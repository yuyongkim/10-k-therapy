import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT_METADATA_KEYS: Tuple[str, ...] = (
    "document_id",
    "source_info",
    "company",
    "processing_info",
    "document_metadata",
    "entity_profile",
    "xbrl_summary",
    "document_intelligence",
)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_dir_name(name: str, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (name or "").strip())
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def validate_schema_payload(payload: Dict[str, Any], source_path: Path) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid payload type: {source_path}")
    if not payload.get("document_id"):
        raise ValueError(f"Missing document_id: {source_path}")
    if not isinstance(payload.get("source_info"), dict):
        raise ValueError(f"Missing source_info object: {source_path}")
    if not isinstance(payload.get("sections"), list):
        raise ValueError(f"Missing sections list: {source_path}")


def build_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for key in ROOT_METADATA_KEYS:
        metadata[key] = payload.get(key)
    return metadata


def build_section_index(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx, section in enumerate(sections):
        mapping = section.get("section_mapping", {}) if isinstance(section.get("section_mapping"), dict) else {}
        content = section.get("content", {}) if isinstance(section.get("content"), dict) else {}
        section_id = str(section.get("section_id") or f"section_{idx + 1}")
        rows.append(
            {
                "section_id": section_id,
                "common_tag": mapping.get("common_tag"),
                "order_index": mapping.get("order_index"),
                "token_count": content.get("token_count", 0),
                "has_tables": bool(content.get("has_tables", False)),
                "has_financial_data": bool(content.get("has_financial_data", False)),
            }
        )
    return rows


def split_single_file(input_path: Path, output_root: Path, overwrite: bool = False) -> Dict[str, Any]:
    payload = load_json(input_path)
    validate_schema_payload(payload, input_path)

    company = payload.get("company", {}) if isinstance(payload.get("company"), dict) else {}
    identifier = str(company.get("identifier") or input_path.parent.name or "unknown")
    rcept_no = input_path.stem

    out_dir = output_root / identifier / rcept_no
    if out_dir.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {out_dir}. Use --overwrite to replace.")
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = build_metadata(payload)
    sections = payload.get("sections", [])
    section_index = build_section_index(sections)

    metadata_path = out_dir / "metadata.json"
    section_index_path = out_dir / "sections" / "section_index.json"

    write_json(metadata_path, metadata)
    write_json(section_index_path, {"sections": section_index})

    section_artifacts: List[Dict[str, Any]] = []
    section_token_sum = 0

    for idx, section in enumerate(sections):
        section_id_raw = str(section.get("section_id") or f"section_{idx + 1}")
        section_dir_name = safe_dir_name(section_id_raw, f"section_{idx + 1:04d}")
        section_dir = out_dir / "sections" / section_dir_name
        content_dir = section_dir / "content"

        mapping = section.get("section_mapping", {}) if isinstance(section.get("section_mapping"), dict) else {}
        content = section.get("content", {}) if isinstance(section.get("content"), dict) else {}
        insights = section.get("extracted_insights", {})

        token_count = int(content.get("token_count") or 0)
        section_token_sum += token_count

        section_meta = {
            "section_id": section_id_raw,
            "section_mapping": mapping,
            "token_count": token_count,
            "has_tables": bool(content.get("has_tables", False)),
            "has_financial_data": bool(content.get("has_financial_data", False)),
        }

        section_meta_path = section_dir / "section_meta.json"
        insights_path = section_dir / "insights.json"
        raw_html_path = content_dir / "raw_html.html"
        plain_text_path = content_dir / "plain_text.txt"

        write_json(section_meta_path, section_meta)
        write_json(insights_path, insights if isinstance(insights, dict) else {"value": insights})
        content_dir.mkdir(parents=True, exist_ok=True)
        raw_html_path.write_text(str(content.get("raw_html", "")), encoding="utf-8")
        plain_text_path.write_text(str(content.get("plain_text", "")), encoding="utf-8")

        section_artifacts.append(
            {
                "section_id": section_id_raw,
                "section_dir": str(section_dir.relative_to(out_dir).as_posix()),
                "token_count": token_count,
                "has_tables": bool(content.get("has_tables", False)),
                "has_financial_data": bool(content.get("has_financial_data", False)),
                "files": {
                    "section_meta": str(section_meta_path.relative_to(out_dir).as_posix()),
                    "insights": str(insights_path.relative_to(out_dir).as_posix()),
                    "raw_html": str(raw_html_path.relative_to(out_dir).as_posix()),
                    "plain_text": str(plain_text_path.relative_to(out_dir).as_posix()),
                },
            }
        )

    processing_info = payload.get("processing_info", {}) if isinstance(payload.get("processing_info"), dict) else {}
    processing_total_tokens = int(processing_info.get("total_tokens") or 0)
    token_sum_match = processing_total_tokens == section_token_sum

    manifest = {
        "split_version": "v1-level-ab",
        "created_at": datetime.now().isoformat(),
        "source": {
            "path": str(input_path.as_posix()),
            "file_name": input_path.name,
            "file_size_bytes": input_path.stat().st_size,
            "sha256": sha256_file(input_path),
        },
        "document": {
            "document_id": payload.get("document_id"),
            "identifier": identifier,
            "rcept_no": rcept_no,
            "system": payload.get("source_info", {}).get("system")
            if isinstance(payload.get("source_info"), dict)
            else None,
        },
        "output": {
            "root_dir": str(out_dir.as_posix()),
            "metadata_path": "metadata.json",
            "section_index_path": "sections/section_index.json",
        },
        "integrity": {
            "section_count": len(sections),
            "section_token_sum": section_token_sum,
            "processing_total_tokens": processing_total_tokens,
            "token_sum_match": token_sum_match,
        },
        "sections": section_artifacts,
    }

    manifest_path = out_dir / "manifest.json"
    write_json(manifest_path, manifest)

    return {
        "status": "ok",
        "input_path": str(input_path.as_posix()),
        "output_dir": str(out_dir.as_posix()),
        "manifest_path": str(manifest_path.as_posix()),
        "section_count": len(sections),
        "section_token_sum": section_token_sum,
        "processing_total_tokens": processing_total_tokens,
        "token_sum_match": token_sum_match,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Split DART unified schema JSON into document/section artifacts.")
    parser.add_argument("--input-json", required=True, help="Path to one unified schema JSON file")
    parser.add_argument(
        "--output-root",
        default="data/dart/unified_schema_split",
        help="Root directory for split outputs",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite if output directory already exists")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    result = split_single_file(input_path=input_path, output_root=output_root, overwrite=args.overwrite)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
