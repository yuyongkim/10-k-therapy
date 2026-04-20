import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from crawler.dart_crawler import OpenDartCrawler
from parser.unified_disclosure_parser import DARTParser, validate_schema_output
from utils.common import setup_logging, load_yaml_config

logger = setup_logging(__name__, log_file="crawler.log")


# Load project .env so DART_API_KEY is available in non-orchestrated runs.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _to_yyyymmdd(value: str) -> str:
    text = (value or "").strip()
    if len(text) == 8 and text.isdigit():
        return text
    try:
        dt = datetime.fromisoformat(text)
        return dt.strftime("%Y%m%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {value}. Use YYYYMMDD or YYYY-MM-DD.")


def _load_config(config_path: str) -> Dict[str, Any]:
    return load_yaml_config(config_path)


def _targets_from_config(config: Dict[str, Any]) -> List[Dict[str, str]]:
    dart_cfg = config.get("dart", {})
    targets = dart_cfg.get("targets", [])
    if isinstance(targets, list):
        normalized = []
        for item in targets:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "corp_code": str(item.get("corp_code", "")).strip(),
                        "stock_code": str(item.get("stock_code", "")).strip(),
                        "corp_name": str(item.get("corp_name", "")).strip(),
                    }
                )
        return normalized
    return []


def _single_target_from_args(args: argparse.Namespace) -> Optional[Dict[str, str]]:
    if args.corp_code or args.stock_code or args.corp_name:
        return {
            "corp_code": (args.corp_code or "").strip(),
            "stock_code": (args.stock_code or "").strip(),
            "corp_name": (args.corp_name or "").strip(),
        }
    return None


def _targets_from_corp_master(crawler: OpenDartCrawler) -> List[Dict[str, str]]:
    rows = crawler.load_corp_codes()
    listed = [row for row in rows if str(row.get("stock_code", "")).strip()]
    listed.sort(key=lambda row: row.get("stock_code", ""))
    return [
        {
            "corp_code": str(item.get("corp_code", "")).strip(),
            "stock_code": str(item.get("stock_code", "")).strip(),
            "corp_name": str(item.get("corp_name", "")).strip(),
        }
        for item in listed
    ]


def _slice_targets(
    targets: List[Dict[str, str]],
    offset: int,
    limit: Optional[int],
) -> List[Dict[str, str]]:
    safe_offset = max(0, int(offset or 0))
    sliced = targets[safe_offset:]
    if limit is None:
        return sliced
    safe_limit = max(0, int(limit))
    return sliced[:safe_limit]


def run_dart_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    config = _load_config(args.config)
    crawler = OpenDartCrawler(args.config)

    single = _single_target_from_args(args)
    if single:
        targets = [single]
    elif args.all_listed:
        targets = _targets_from_corp_master(crawler)
    else:
        targets = _targets_from_config(config)

    targets = _slice_targets(
        targets=targets,
        offset=args.target_offset,
        limit=args.target_limit,
    )

    if not targets:
        raise ValueError(
            "No DART target specified. Pass --corp-code/--stock-code/--corp-name "
            "or configure dart.targets in config.yaml. You can also use --all-listed."
        )

    dart_cfg = config.get("dart", {})
    bgn_de = _to_yyyymmdd(args.start_date or dart_cfg.get("date_range", {}).get("start", "20240101"))
    end_de = _to_yyyymmdd(args.end_date or dart_cfg.get("date_range", {}).get("end", datetime.now().strftime("%Y%m%d")))
    max_filings = int(args.max_filings or dart_cfg.get("max_filings", 5))
    include_quarterly = bool(args.include_quarterly or dart_cfg.get("include_quarterly", False))
    skip_existing = bool(args.skip_existing)

    run_rows: List[Dict[str, Any]] = []
    success_count = 0
    fail_count = 0
    skipped_count = 0

    logger.info(
        "DART target selection: total=%d, offset=%d, limit=%s, all_listed=%s",
        len(targets),
        max(0, int(args.target_offset or 0)),
        str(args.target_limit),
        str(bool(args.all_listed)),
    )

    for target in targets:
        target_name = target.get("corp_name")
        target_stock = target.get("stock_code")
        try:
            corp_code, corp_meta = crawler.resolve_corp_code(
                corp_code=target.get("corp_code"),
                stock_code=target_stock,
                corp_name=target_name,
            )
            company_info = crawler.get_company_info(corp_code)
            logger.info(
                "Resolved DART target: corp_code=%s corp_name=%s stock_code=%s",
                corp_code,
                corp_meta.get("corp_name"),
                corp_meta.get("stock_code"),
            )
        except Exception as exc:
            logger.warning(
                "Skipping target (resolve/company failed): corp_name=%s stock_code=%s err=%s",
                target_name,
                target_stock,
                str(exc),
            )
            run_rows.append(
                {
                    "corp_code": target.get("corp_code"),
                    "corp_name": target_name,
                    "stock_code": target_stock,
                    "status": "target_failed",
                    "error": str(exc),
                }
            )
            fail_count += 1
            continue

        try:
            filings = crawler.collect_business_reports(
                corp_code=corp_code,
                bgn_de=bgn_de,
                end_de=end_de,
                include_quarterly=include_quarterly,
                max_items=max_filings,
            )
        except Exception as exc:
            text = str(exc)
            if "013" in text:
                logger.info(
                    "No filing data for target: corp_code=%s stock_code=%s",
                    corp_code,
                    corp_meta.get("stock_code"),
                )
                run_rows.append(
                    {
                        "corp_code": corp_code,
                        "corp_name": corp_meta.get("corp_name"),
                        "stock_code": corp_meta.get("stock_code"),
                        "status": "no_data",
                        "error": text,
                    }
                )
                continue

            logger.warning(
                "Skipping target (collect failed): corp_code=%s stock_code=%s err=%s",
                corp_code,
                corp_meta.get("stock_code"),
                text,
            )
            run_rows.append(
                {
                    "corp_code": corp_code,
                    "corp_name": corp_meta.get("corp_name"),
                    "stock_code": corp_meta.get("stock_code"),
                    "status": "collect_failed",
                    "error": text,
                }
            )
            fail_count += 1
            continue

        logger.info("Found %d DART filings for corp_code=%s", len(filings), corp_code)
        if not filings:
            run_rows.append(
                {
                    "corp_code": corp_code,
                    "corp_name": corp_meta.get("corp_name"),
                    "stock_code": corp_meta.get("stock_code"),
                    "status": "no_filings",
                }
            )
            continue

        for filing in filings:
            rcept_no = str(filing.get("rcept_no", "")).strip()
            out_dir = crawler.schema_dir / corp_code
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{rcept_no}.json"

            if skip_existing and out_path.exists():
                run_rows.append(
                    {
                        "corp_code": corp_code,
                        "corp_name": filing.get("corp_name") or corp_meta.get("corp_name"),
                        "rcept_no": rcept_no,
                        "report_nm": filing.get("report_nm"),
                        "rcept_dt": filing.get("rcept_dt"),
                        "viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}" if rcept_no else None,
                        "status": "skipped_existing",
                        "schema_output_path": str(out_path),
                    }
                )
                skipped_count += 1
                continue

            row: Dict[str, Any] = {
                "corp_code": corp_code,
                "corp_name": filing.get("corp_name") or corp_meta.get("corp_name"),
                "rcept_no": rcept_no,
                "report_nm": filing.get("report_nm"),
                "rcept_dt": filing.get("rcept_dt"),
                "viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}" if rcept_no else None,
            }
            try:
                downloaded = crawler.download_filing_document(
                    filing_row=filing,
                    corp_code=corp_code,
                    company_info=company_info,
                )
                parser = DARTParser(
                    html_path=str(downloaded["primary_document_path"]),
                    metadata_path=str(downloaded["metadata_path"]),
                )
                schema = parser.to_schema_json()
                is_valid = validate_schema_output(schema)

                out_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

                row.update(
                    {
                        "status": "ok",
                        "schema_valid": is_valid,
                        "primary_document_path": str(downloaded["primary_document_path"]),
                        "schema_output_path": str(out_path),
                    }
                )
                success_count += 1
            except Exception as exc:
                logger.exception("Failed DART filing processing: corp_code=%s rcept_no=%s", corp_code, rcept_no)
                row.update({"status": "failed", "error": str(exc)})
                fail_count += 1
            run_rows.append(row)

    summary = {
        "run_at": datetime.now().isoformat(),
        "config_path": args.config,
        "date_range": {"start": bgn_de, "end": end_de},
        "target_mode": "all_listed" if args.all_listed else ("single" if single else "config_targets"),
        "target_offset": max(0, int(args.target_offset or 0)),
        "target_limit": args.target_limit,
        "target_count": len(targets),
        "filing_attempts": len(run_rows),
        "success": success_count,
        "failed": fail_count,
        "skipped_existing": skipped_count,
        "include_quarterly": include_quarterly,
        "skip_existing": skip_existing,
        "max_filings_per_target": max_filings,
        "rows": run_rows,
    }

    summary_path = crawler.schema_dir / f"run_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved DART run summary: %s", summary_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DART-only filing pipeline and unified schema generation")
    parser.add_argument("--config", default="config.yaml", help="Path to config yaml")
    parser.add_argument("--corp-code", default=None, help="DART corp_code (8 digits)")
    parser.add_argument("--stock-code", default=None, help="KRX stock code (6 digits)")
    parser.add_argument("--corp-name", default=None, help="Korean/English corporation name")
    parser.add_argument("--all-listed", action="store_true", help="Use all listed corporations from corp_code master (stock_code present)")
    parser.add_argument("--target-offset", type=int, default=0, help="Target list start offset (for chunk processing)")
    parser.add_argument("--target-limit", type=int, default=None, help="Max number of targets to process after offset")
    parser.add_argument("--start-date", default=None, help="Start date: YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="End date: YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--max-filings", type=int, default=None, help="Max filings per target")
    parser.add_argument("--include-quarterly", action="store_true", help="Include quarterly and half-year reports")
    parser.set_defaults(skip_existing=True)
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", help="Skip filings that already have schema output (default)")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false", help="Reprocess filings even if schema output already exists")
    args = parser.parse_args()

    result = run_dart_pipeline(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
