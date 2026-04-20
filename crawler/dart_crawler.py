import io
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import requests

from utils.common import setup_logging, load_yaml_config

logger = setup_logging(__name__, log_file="crawler.log")


class OpenDartCrawler:
    """
    OpenDART crawler for filing metadata and original report documents.

    Official endpoints used:
    - https://opendart.fss.or.kr/api/list.json
    - https://opendart.fss.or.kr/api/company.json
    - https://opendart.fss.or.kr/api/corpCode.xml
    - https://opendart.fss.or.kr/api/document.xml
    """

    API_BASE = "https://opendart.fss.or.kr/api"
    SUCCESS_CODE = "000"
    DEFAULT_USER_AGENT = "sec-license-extraction/1.0"

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = load_yaml_config(config_path)

        self.dart_config = self.config.get("dart", {})
        self.paths = self.config.get("paths", {})
        data_dir = Path(self.paths.get("data_dir", "data"))
        self.dart_data_dir = data_dir / "dart"
        self.raw_dir = Path(self.paths.get("dart_raw_filings", str(self.dart_data_dir / "raw_filings")))
        self.schema_dir = Path(self.paths.get("dart_unified_schema", str(self.dart_data_dir / "unified_schema")))
        self.corp_code_cache = Path(self.paths.get("dart_corp_code_cache", str(self.dart_data_dir / "corp_code.xml")))

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.schema_dir.mkdir(parents=True, exist_ok=True)
        self.corp_code_cache.parent.mkdir(parents=True, exist_ok=True)

        self.api_key = (
            os.getenv("DART_API_KEY")
            or self.dart_config.get("api_key")
            or ""
        ).strip()
        if not self.api_key:
            raise ValueError("DART API key is required. Set DART_API_KEY in environment.")

        self.rate_limit_per_sec = float(self.dart_config.get("rate_limit", 4.0))
        self._min_interval = 1.0 / max(self.rate_limit_per_sec, 1.0)
        self._last_request_ts = 0.0

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.dart_config.get("user_agent", self.DEFAULT_USER_AGENT),
                "Accept": "*/*",
            }
        )

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_ts
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.time()

    def _request(self, endpoint: str, params: Dict[str, Any], timeout: int = 30) -> requests.Response:
        self._throttle()
        url = f"{self.API_BASE}/{endpoint}"
        resp = self.session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _request_json(self, endpoint: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        payload = dict(params)
        payload["crtfc_key"] = self.api_key
        resp = self._request(endpoint, payload, timeout=timeout)
        data = resp.json()
        status = str(data.get("status", ""))
        if status != self.SUCCESS_CODE:
            message = data.get("message", "Unknown DART API error")
            raise RuntimeError(f"DART API error ({endpoint}): {status} {message}")
        return data

    def _request_binary(self, endpoint: str, params: Dict[str, Any], timeout: int = 60) -> bytes:
        payload = dict(params)
        payload["crtfc_key"] = self.api_key
        resp = self._request(endpoint, payload, timeout=timeout)
        return resp.content

    @staticmethod
    def parse_corp_code_xml(xml_bytes: bytes) -> List[Dict[str, str]]:
        root = ET.fromstring(xml_bytes)
        items: List[Dict[str, str]] = []
        for node in root.findall(".//list"):
            items.append(
                {
                    "corp_code": (node.findtext("corp_code") or "").strip(),
                    "corp_name": (node.findtext("corp_name") or "").strip(),
                    "stock_code": (node.findtext("stock_code") or "").strip(),
                    "modify_date": (node.findtext("modify_date") or "").strip(),
                }
            )
        return items

    def update_corp_code_cache(self, force: bool = False) -> Path:
        if self.corp_code_cache.exists() and not force:
            return self.corp_code_cache

        logger.info("Downloading DART corp code master ...")
        zipped = self._request_binary("corpCode.xml", {})

        with zipfile.ZipFile(io.BytesIO(zipped)) as zf:
            xml_names = [name for name in zf.namelist() if name.lower().endswith(".xml")]
            if not xml_names:
                raise RuntimeError("corpCode.xml response does not include XML payload")
            xml_data = zf.read(xml_names[0])

        self.corp_code_cache.write_bytes(xml_data)
        logger.info("Saved corp code cache: %s", self.corp_code_cache)
        return self.corp_code_cache

    def load_corp_codes(self) -> List[Dict[str, str]]:
        cache_path = self.update_corp_code_cache(force=False)
        xml_data = cache_path.read_bytes()
        return self.parse_corp_code_xml(xml_data)

    def resolve_corp_code(
        self,
        corp_code: Optional[str] = None,
        stock_code: Optional[str] = None,
        corp_name: Optional[str] = None,
    ) -> Tuple[str, Dict[str, str]]:
        if corp_code:
            target = corp_code.strip()
            matched = next(
                (row for row in self.load_corp_codes() if row["corp_code"] == target),
                {"corp_code": target, "corp_name": corp_name or "", "stock_code": stock_code or ""},
            )
            return target, matched

        rows = self.load_corp_codes()
        if stock_code:
            target_stock = stock_code.strip()
            for row in rows:
                if row["stock_code"] == target_stock:
                    return row["corp_code"], row
        if corp_name:
            needle = corp_name.strip().lower()
            exact = [row for row in rows if row["corp_name"].lower() == needle]
            if exact:
                return exact[0]["corp_code"], exact[0]
            fuzzy = [row for row in rows if needle in row["corp_name"].lower()]
            if fuzzy:
                return fuzzy[0]["corp_code"], fuzzy[0]

        raise ValueError("Unable to resolve corp_code. Provide corp_code, stock_code, or corp_name.")

    def get_company_info(self, corp_code: str) -> Dict[str, Any]:
        return self._request_json("company.json", {"corp_code": corp_code})

    def list_filings(
        self,
        corp_code: str,
        bgn_de: str,
        end_de: str,
        page_no: int = 1,
        page_count: int = 100,
        pblntf_ty: str = "A",
        pblntf_detail_ty: Optional[str] = None,
        last_reprt_at: str = "Y",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": page_no,
            "page_count": page_count,
            "last_reprt_at": last_reprt_at,
            "pblntf_ty": pblntf_ty,
        }
        if pblntf_detail_ty:
            params["pblntf_detail_ty"] = pblntf_detail_ty
        return self._request_json("list.json", params)

    def collect_business_reports(
        self,
        corp_code: str,
        bgn_de: str,
        end_de: str,
        include_quarterly: bool = False,
        max_items: int = 20,
    ) -> List[Dict[str, Any]]:
        detail_types = ["A001"] if not include_quarterly else ["A001", "A002", "A003"]
        collected: List[Dict[str, Any]] = []

        for detail in detail_types:
            page_no = 1
            while True:
                data = self.list_filings(
                    corp_code=corp_code,
                    bgn_de=bgn_de,
                    end_de=end_de,
                    page_no=page_no,
                    page_count=100,
                    pblntf_ty="A",
                    pblntf_detail_ty=detail,
                    last_reprt_at="Y",
                )
                rows = data.get("list", [])
                if not rows:
                    break
                collected.extend(rows)

                total_count = int(data.get("total_count", 0) or 0)
                if len(collected) >= min(total_count, max_items):
                    break
                total_page = int(data.get("total_page", 1) or 1)
                if page_no >= total_page:
                    break
                page_no += 1

        # Deduplicate by receipt number and sort latest first.
        uniq: Dict[str, Dict[str, Any]] = {}
        for row in collected:
            rcp_no = str(row.get("rcept_no", "")).strip()
            if rcp_no and rcp_no not in uniq:
                uniq[rcp_no] = row
        output = sorted(
            uniq.values(),
            key=lambda x: x.get("rcept_dt", ""),
            reverse=True,
        )
        return output[:max_items]

    def _decode_document_error(self, blob: bytes) -> Optional[str]:
        stripped = blob.lstrip()
        if not stripped.startswith(b"<?xml"):
            return None
        try:
            root = ET.fromstring(blob)
            status = (root.findtext(".//status") or "").strip()
            message = (root.findtext(".//message") or "").strip()
            if status and status != self.SUCCESS_CODE:
                return f"{status} {message}"
        except ET.ParseError:
            return None
        return None

    @staticmethod
    def _pick_primary_document_file(extract_dir: Path) -> Optional[Path]:
        if not extract_dir.exists():
            return None

        files = [p for p in extract_dir.rglob("*") if p.is_file()]
        if not files:
            return None

        def score(path: Path) -> Tuple[int, int]:
            ext = path.suffix.lower()
            if ext in {".xhtml", ".html", ".htm"}:
                pri = 0
            elif ext in {".xml"}:
                pri = 1
            elif ext in {".txt"}:
                pri = 2
            else:
                pri = 3
            return pri, -path.stat().st_size

        files.sort(key=score)
        return files[0]

    def download_filing_document(
        self,
        filing_row: Dict[str, Any],
        corp_code: str,
        company_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rcept_no = str(filing_row.get("rcept_no") or "").strip()
        if not rcept_no:
            raise ValueError("filing_row missing rcept_no")

        save_dir = self.raw_dir / corp_code / rcept_no
        save_dir.mkdir(parents=True, exist_ok=True)

        metadata_path = save_dir / "filing_metadata.json"
        zip_path = save_dir / "document.zip"
        extract_dir = save_dir / "document_files"
        extract_dir.mkdir(parents=True, exist_ok=True)

        blob = self._request_binary("document.xml", {"rcept_no": rcept_no})
        err = self._decode_document_error(blob)
        if err:
            raise RuntimeError(f"DART document download failed ({rcept_no}): {err}")

        zip_path.write_bytes(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            zf.extractall(extract_dir)

        primary_file = self._pick_primary_document_file(extract_dir)
        if primary_file is None:
            raise RuntimeError(f"No extractable document file found for receipt {rcept_no}")

        meta_payload = {
            "source": "DART",
            "corp_code": corp_code,
            "rcept_no": rcept_no,
            "filing": filing_row,
            "company_info": company_info or {},
            "primary_document_path": str(primary_file),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        metadata_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "rcept_no": rcept_no,
            "metadata_path": metadata_path,
            "primary_document_path": primary_file,
            "raw_dir": save_dir,
        }

