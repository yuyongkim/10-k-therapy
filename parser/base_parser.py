"""DocumentParser base class for SEC/DART disclosure parsing."""

import json
import re
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

from .constants import (
    AMOUNT_RE,
    COMMON_TO_DART_LABEL,
    COMMON_TO_SEC_LABEL,
    CURRENCY_CODE_RE,
    FINANCIAL_SIGNAL_RE,
    INSIGHT_KEYWORDS,
    PARSER_VERSION,
    PERCENT_RE,
    SEC_KEY_METRIC_CONCEPTS,
    YEAR_RE,
)
from .utils import clean_text, decode_document_bytes, safe_text, tag_attr, to_float


class DocumentParser:
    """Common SEC/DART disclosure parser that produces a unified schema JSON."""

    def __init__(
        self,
        html_path: str,
        source_type: str,
        metadata_path: Optional[str] = None,
        parser_version: str = PARSER_VERSION,
        max_html_chars: int = 50000,
    ):
        self.html_path = Path(html_path)
        self.source_type = source_type.upper().strip()
        self.parser_version = parser_version
        self.max_html_chars = max_html_chars

        if self.source_type not in {"SEC", "DART"}:
            raise ValueError("source_type must be 'SEC' or 'DART'")
        if not self.html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {self.html_path}")

        self.raw_bytes = self.html_path.read_bytes()
        self.html_content = decode_document_bytes(self.raw_bytes)
        # DART files often contain XML declaration with malformed HTML-like content.
        # Use tolerant HTML parser for DART to avoid truncation on broken tags.
        if self.source_type == "DART":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                self.soup = BeautifulSoup(self.html_content, "lxml")
        else:
            parser_backend = "xml" if self.html_content.lstrip().startswith("<?xml") else "lxml"
            self.soup = BeautifulSoup(self.html_content, parser_backend)
        self.full_text = clean_text(self.soup.get_text(" ", strip=True))

        self.metadata_path = Path(metadata_path) if metadata_path else self._default_metadata_path()
        self.file_metadata = self._load_json(self.metadata_path) if self.metadata_path else {}
        self._license_insights: Optional[Dict[str, Any]] = None
        self._sections_cache: Optional[List[Dict[str, Any]]] = None

    def _default_metadata_path(self) -> Optional[Path]:
        candidate = self.html_path.parent / "filing_metadata.json"
        return candidate if candidate.exists() else None

    @staticmethod
    def _load_json(path: Optional[Path]) -> Dict[str, Any]:
        if path is None or not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return {}

    def _ix_value(self, name: str) -> str:
        tag = self.soup.find(attrs={"name": name})
        return clean_text(tag.get_text(" ", strip=True)) if tag else ""

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Fast approximation for chunking/LLM planning.
        return max(1, int(len(clean_text(text).split()) * 1.3))

    def _get_sections_info(self) -> List[Dict[str, Any]]:
        if self._sections_cache is None:
            self._sections_cache = self.identify_sections()
        return self._sections_cache

    def extract_document_metadata(self) -> Dict[str, Any]:
        filing_meta = (
            self.file_metadata.get("filing", {})
            if isinstance(self.file_metadata.get("filing"), dict)
            else {}
        )
        company_meta = (
            self.file_metadata.get("company_info", {})
            if isinstance(self.file_metadata.get("company_info"), dict)
            else {}
        )

        company_name = (
            self.file_metadata.get("company_name")
            or filing_meta.get("corp_name")
            or company_meta.get("corp_name_eng")
            or company_meta.get("corp_name")
            or self._ix_value("dei:EntityRegistrantName")
            or "Unknown Company"
        )
        identifier = (
            self.file_metadata.get("cik")
            or self.file_metadata.get("corp_code")
            or filing_meta.get("corp_code")
            or company_meta.get("corp_code")
            or self._ix_value("dei:EntityCentralIndexKey")
            or "UNKNOWN"
        )
        filing_date = (
            self.file_metadata.get("filingDate")
            or self.file_metadata.get("filing_date")
            or filing_meta.get("rcept_dt")
            or ""
        )
        period_end = self.file_metadata.get("reportDate") or self.file_metadata.get("period_end") or ""
        if not period_end and self.source_type == "DART":
            report_nm = safe_text(filing_meta.get("report_nm"))
            month_match = re.search(r"\((\d{4})\.(\d{1,2})\)", report_nm)
            if month_match:
                yy = month_match.group(1)
                mm = month_match.group(2).zfill(2)
                period_end = f"{yy}-{mm}-01"
        fiscal_year = period_end[:4] if period_end else (filing_date[:4] if filing_date else "")

        if self.source_type == "SEC":
            document_type = self.file_metadata.get("form") or self._ix_value("dei:DocumentType") or "10-K"
            language = "en"
        else:
            document_type = (
                self.file_metadata.get("form")
                or filing_meta.get("report_nm")
                or "\uC0AC\uC5C5\uBCF4\uACE0\uC11C"
            )
            language = "ko"

        section_markers = [item["raw_label"] for item in self._get_sections_info()]
        table_count = len(self.soup.find_all("table"))
        has_toc = bool(re.search(r"table\s+of\s+contents", self.full_text, flags=re.IGNORECASE))

        return {
            "company_name": company_name,
            "identifier": identifier,
            "fiscal_year": fiscal_year,
            "filing_date": filing_date,
            "period_end": period_end,
            "document_type": document_type,
            "language": language,
            "total_pages": None,
            "html_structure": {
                "has_table_of_contents": has_toc,
                "section_markers": section_markers,
                "table_count": table_count,
                "estimated_tokens": self._estimate_tokens(self.full_text),
            },
        }

    @staticmethod
    def _normalize_date_token(token: str) -> str:
        text = safe_text(token)
        if not text:
            return ""
        text = text.replace(".", "-").replace("/", "-")
        if re.fullmatch(r"\d{8}", text):
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        return text

    def _extract_context_details(self) -> Dict[str, Dict[str, Any]]:
        context_rows: Dict[str, Dict[str, Any]] = {}
        for tag in self.soup.find_all(True):
            if not tag.name.lower().endswith("context"):
                continue
            context_id = safe_text(tag.get("id"))
            if not context_id:
                continue

            instant = tag.find(lambda x: isinstance(x, Tag) and x.name.lower().endswith("instant"))
            end_date = tag.find(lambda x: isinstance(x, Tag) and x.name.lower().endswith("enddate"))
            start_date = tag.find(lambda x: isinstance(x, Tag) and x.name.lower().endswith("startdate"))
            explicit_members = tag.find_all(
                lambda x: isinstance(x, Tag) and x.name.lower().endswith(("explicitmember", "typedmember"))
            )

            dimensions: List[Dict[str, str]] = []
            for member in explicit_members:
                dimensions.append(
                    {
                        "dimension": tag_attr(member, "dimension"),
                        "value": clean_text(member.get_text(" ", strip=True)),
                    }
                )

            context_rows[context_id] = {
                "start_date": self._normalize_date_token(start_date.get_text(" ", strip=True)) if start_date else "",
                "end_date": self._normalize_date_token(end_date.get_text(" ", strip=True)) if end_date else "",
                "instant": self._normalize_date_token(instant.get_text(" ", strip=True)) if instant else "",
                "dimensions": dimensions,
            }
        return context_rows

    def _extract_context_dates(self) -> Dict[str, str]:
        context_dates: Dict[str, str] = {}
        for context_id, detail in self._extract_context_details().items():
            chosen = detail.get("instant") or detail.get("end_date") or detail.get("start_date") or ""
            if chosen:
                context_dates[context_id] = chosen
        return context_dates

    def _extract_unit_details(self) -> Dict[str, Dict[str, Any]]:
        units: Dict[str, Dict[str, Any]] = {}
        for tag in self.soup.find_all(True):
            if not tag.name.lower().endswith("unit"):
                continue
            unit_id = safe_text(tag.get("id"))
            if not unit_id:
                continue
            measures = [
                clean_text(node.get_text(" ", strip=True))
                for node in tag.find_all(lambda x: isinstance(x, Tag) and x.name.lower().endswith("measure"))
                if clean_text(node.get_text(" ", strip=True))
            ]
            units[unit_id] = {
                "measures": measures,
                "display": " / ".join(measures[:2]) if measures else "",
            }
        return units

    def _collect_fact_nodes(self) -> List[Dict[str, Any]]:
        facts: List[Dict[str, Any]] = []
        for tag in self.soup.find_all(True):
            concept = tag_attr(tag, "name")
            if not concept:
                continue
            value_raw = clean_text(tag.get_text(" ", strip=True))
            if not value_raw:
                continue
            facts.append(
                {
                    "tag_name": tag.name,
                    "concept": concept,
                    "context_ref": tag_attr(tag, "contextRef"),
                    "unit_ref": tag_attr(tag, "unitRef"),
                    "decimals": tag_attr(tag, "decimals"),
                    "value_raw": value_raw,
                    "value_num": to_float(value_raw),
                }
            )
        return facts

    def _pick_latest_fact_for_concepts(
        self,
        concepts: List[str],
        facts: List[Dict[str, Any]],
        context_dates: Dict[str, str],
        context_details: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        concept_set = set(concepts)
        for fact in facts:
            if fact["concept"] not in concept_set:
                continue
            ctx = fact.get("context_ref") or ""
            fact_date = context_dates.get(ctx, "")
            dimension_count = len(context_details.get(ctx, {}).get("dimensions", []))
            candidates.append({**fact, "fact_date": fact_date, "dimension_count": dimension_count})

        if not candidates:
            return None

        def sort_key(item: Dict[str, Any]) -> Tuple[str, int, int]:
            # Prefer latest dated context, then numeric values, then non-dimensional facts.
            date_key = item.get("fact_date") or ""
            numeric_preference = 1 if isinstance(item.get("value_num"), float) else 0
            dimension_preference = -int(item.get("dimension_count", 0))
            return (date_key, numeric_preference, dimension_preference)

        chosen = sorted(candidates, key=sort_key, reverse=True)[0]
        return chosen

    def _extract_metric_history(
        self,
        metric_concepts: List[str],
        facts: List[Dict[str, Any]],
        context_dates: Dict[str, str],
        context_details: Dict[str, Dict[str, Any]],
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        concept_rank = {concept: idx for idx, concept in enumerate(metric_concepts)}
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for fact in facts:
            concept = fact.get("concept")
            if concept not in concept_rank:
                continue
            ctx = fact.get("context_ref") or ""
            period = context_dates.get(ctx, "")
            if not period:
                continue
            grouped.setdefault(period, []).append(
                {
                    **fact,
                    "period": period,
                    "dimension_count": len(context_details.get(ctx, {}).get("dimensions", [])),
                    "concept_rank": concept_rank[concept],
                }
            )

        history: List[Dict[str, Any]] = []
        for period in sorted(grouped.keys(), reverse=True):
            best = sorted(
                grouped[period],
                key=lambda x: (
                    x.get("dimension_count", 0),
                    x.get("concept_rank", 999),
                    0 if isinstance(x.get("value_num"), float) else 1,
                ),
            )[0]
            history.append(
                {
                    "period": period,
                    "value": best.get("value_num"),
                    "value_raw": best.get("value_raw"),
                    "concept": best.get("concept"),
                    "unit_ref": best.get("unit_ref"),
                    "context_ref": best.get("context_ref"),
                    "dimension_count": best.get("dimension_count"),
                }
            )
            if len(history) >= limit:
                break
        return history

    def _extract_entity_profile(self) -> Dict[str, Any]:
        if self.source_type != "SEC":
            return {}
        shares_outstanding = to_float(self._ix_value("dei:EntityCommonStockSharesOutstanding"))
        return {
            "registrant_name": self._ix_value("dei:EntityRegistrantName"),
            "trading_symbol": self._ix_value("dei:TradingSymbol") or safe_text(self.file_metadata.get("ticker")),
            "document_type": self._ix_value("dei:DocumentType"),
            "fiscal_year_focus": self._ix_value("dei:DocumentFiscalYearFocus"),
            "fiscal_period_focus": self._ix_value("dei:DocumentFiscalPeriodFocus"),
            "period_end_date": self._normalize_date_token(self._ix_value("dei:DocumentPeriodEndDate")),
            "amendment_flag": self._ix_value("dei:AmendmentFlag"),
            "shares_outstanding": shares_outstanding,
        }

    def _extract_sec_xbrl_summary(self) -> Dict[str, Any]:
        if self.source_type != "SEC":
            return {}

        facts = self._collect_fact_nodes()
        if not facts:
            return {}
        context_details = self._extract_context_details()
        context_dates = self._extract_context_dates()
        unit_details = self._extract_unit_details()

        key_metrics: Dict[str, Any] = {}
        metric_history: Dict[str, List[Dict[str, Any]]] = {}
        for metric, concepts in SEC_KEY_METRIC_CONCEPTS.items():
            picked = self._pick_latest_fact_for_concepts(concepts, facts, context_dates, context_details)
            if picked:
                key_metrics[metric] = {
                    "value": picked.get("value_num"),
                    "value_raw": picked.get("value_raw"),
                    "concept": picked.get("concept"),
                    "context_ref": picked.get("context_ref"),
                    "period": picked.get("fact_date"),
                    "unit_ref": picked.get("unit_ref"),
                    "unit_display": unit_details.get(picked.get("unit_ref", ""), {}).get("display", ""),
                    "dimension_count": picked.get("dimension_count"),
                }
            history_rows = self._extract_metric_history(concepts, facts, context_dates, context_details)
            if history_rows:
                metric_history[metric] = history_rows

        concept_prefix_counts: Counter = Counter()
        concept_counts: Counter = Counter()
        for fact in facts:
            concept = fact.get("concept", "")
            prefix = concept.split(":")[0] if ":" in concept else "unknown"
            concept_prefix_counts[prefix] += 1
            concept_counts[concept] += 1

        dimensions_counter: Counter = Counter()
        for row in context_details.values():
            for dim in row.get("dimensions", []):
                dimensions_counter[safe_text(dim.get("dimension"))] += 1

        available_periods = sorted({d for d in context_dates.values() if d}, reverse=True)
        numeric_facts = [f for f in facts if isinstance(f.get("value_num"), float)]
        dated_facts = [f for f in facts if context_dates.get(f.get("context_ref") or "")]

        return {
            "total_facts": len(facts),
            "numeric_fact_count": len(numeric_facts),
            "dated_fact_count": len(dated_facts),
            "key_metrics": key_metrics,
            "metric_history": metric_history,
            "available_periods": available_periods[:16],
            "taxonomy_prefix_distribution": dict(concept_prefix_counts.most_common(20)),
            "top_concepts": dict(concept_counts.most_common(25)),
            "context_summary": {
                "total_contexts": len(context_details),
                "contexts_with_dimensions": sum(
                    1 for row in context_details.values() if row.get("dimensions")
                ),
                "top_dimensions": dict(dimensions_counter.most_common(20)),
            },
            "unit_summary": {
                "total_units": len(unit_details),
                "units": unit_details,
            },
        }

    def identify_sections(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def _extract_section_blob(
        self,
        heading_tag: Tag,
        next_heading_tag: Optional[Tag],
    ) -> Dict[str, Any]:
        html_chunks: List[str] = []
        text_chunks: List[str] = []
        has_tables = False

        current: Optional[Any] = heading_tag
        while current is not None:
            if current is next_heading_tag:
                break
            if isinstance(current, Tag):
                html_chunks.append(str(current))
                chunk_text = clean_text(current.get_text(" ", strip=True))
                if chunk_text:
                    text_chunks.append(chunk_text)
                if current.name == "table" or current.find("table") is not None:
                    has_tables = True
            elif isinstance(current, NavigableString):
                text_value = clean_text(str(current))
                if text_value:
                    text_chunks.append(text_value)
            current = current.next_sibling

        raw_html = "".join(html_chunks)
        plain_text = clean_text(" ".join(text_chunks))
        return {
            "raw_html": raw_html[: self.max_html_chars],
            "plain_text": plain_text,
            "token_count": self._estimate_tokens(plain_text),
            "has_tables": has_tables,
            "has_financial_data": bool(FINANCIAL_SIGNAL_RE.search(plain_text)),
        }

    def extract_section_content(self, section_info: Dict[str, Any]) -> Dict[str, Any]:
        heading_tag = section_info.get("_heading_tag")
        next_heading_tag = section_info.get("_next_heading_tag")
        if not isinstance(heading_tag, Tag):
            return {
                "raw_html": "",
                "plain_text": "",
                "token_count": 0,
                "has_tables": False,
                "has_financial_data": False,
            }
        return self._extract_section_blob(heading_tag, next_heading_tag)

    def _normalize_license_insights(self, license_data: Any) -> Dict[str, Any]:
        if isinstance(license_data, dict):
            if "license_costs" in license_data and isinstance(license_data["license_costs"], dict):
                return license_data["license_costs"]
            if {"total_annual_cost", "major_licenses"}.issubset(set(license_data.keys())):
                return license_data

        agreements_flat: List[Dict[str, Any]] = []
        source_locations: List[str] = []

        if isinstance(license_data, list):
            for item in license_data:
                if not isinstance(item, dict):
                    continue
                source_note = item.get("source_note", {}) if isinstance(item.get("source_note"), dict) else {}
                source_loc = ""
                if source_note.get("note_number"):
                    source_loc = f"Note {source_note['note_number']}"
                elif source_note.get("note_title"):
                    source_loc = safe_text(source_note["note_title"])[:80]
                if source_loc:
                    source_locations.append(source_loc)

                extraction = item.get("extraction", {}) if isinstance(item.get("extraction"), dict) else {}
                for agreement in extraction.get("agreements", []):
                    if not isinstance(agreement, dict):
                        continue
                    terms = agreement.get("financial_terms", {}) if isinstance(agreement.get("financial_terms"), dict) else {}
                    upfront = terms.get("upfront_payment", {}) if isinstance(terms.get("upfront_payment"), dict) else {}
                    contract_terms = agreement.get("contract_terms", {}) if isinstance(agreement.get("contract_terms"), dict) else {}
                    term = contract_terms.get("term", {}) if isinstance(contract_terms.get("term"), dict) else {}
                    parties = agreement.get("parties", {}) if isinstance(agreement.get("parties"), dict) else {}
                    licensor = parties.get("licensor", {}) if isinstance(parties.get("licensor"), dict) else {}
                    metadata = agreement.get("metadata", {}) if isinstance(agreement.get("metadata"), dict) else {}

                    cost_value = to_float(upfront.get("amount"))
                    currency = safe_text(upfront.get("currency")).upper() or None
                    confidence = to_float(metadata.get("confidence_score"))
                    years = to_float(term.get("years"))
                    if years and years > 0 and cost_value is not None:
                        annualized = cost_value / years
                    else:
                        annualized = cost_value

                    agreements_flat.append(
                        {
                            "licensor": safe_text(licensor.get("name")) or "Unknown",
                            "cost": annualized,
                            "raw_amount": cost_value,
                            "currency": currency,
                            "type": safe_text(agreement.get("technology", {}).get("category"))
                            if isinstance(agreement.get("technology"), dict)
                            else "license",
                            "contract_period": safe_text(term.get("years")),
                            "confidence": confidence,
                        }
                    )

        numeric_costs = [item["cost"] for item in agreements_flat if isinstance(item.get("cost"), float)]
        total_annual_cost = round(sum(numeric_costs), 2) if numeric_costs else None
        currency_values = [item["currency"] for item in agreements_flat if item.get("currency")]
        currency = Counter(currency_values).most_common(1)[0][0] if currency_values else "USD"
        confidences = [item["confidence"] for item in agreements_flat if isinstance(item.get("confidence"), float)]

        major_licenses: List[Dict[str, Any]] = []
        sorted_agreements = sorted(
            agreements_flat,
            key=lambda x: (x.get("cost") is None, -(x.get("cost") or 0)),
        )
        for item in sorted_agreements[:5]:
            major_licenses.append(
                {
                    "licensor": item.get("licensor"),
                    "cost": item.get("cost"),
                    "type": item.get("type") or "license",
                    "contract_period": item.get("contract_period") or None,
                }
            )

        return {
            "total_annual_cost": total_annual_cost,
            "currency": currency,
            "major_licenses": major_licenses,
            "analysis_confidence": round(mean(confidences), 4) if confidences else None,
            "source_location": ", ".join(sorted(set(source_locations))) if source_locations else "",
        }

    def integrate_license_analysis(self, license_data: Any) -> None:
        """Integrate existing license extraction results into section insights."""
        self._license_insights = self._normalize_license_insights(license_data)

    def _build_document_id(self, meta: Dict[str, Any]) -> str:
        source = self.source_type
        ident = re.sub(r"[^A-Za-z0-9]+", "", safe_text(meta.get("identifier"))) or "UNKNOWN"
        year = re.sub(r"[^0-9]", "", safe_text(meta.get("fiscal_year"))) or "0000"
        doc_type = re.sub(r"[^A-Za-z0-9]+", "", safe_text(meta.get("document_type"))) or "DOC"
        return f"{source}_{ident}_{year}_{doc_type}"

    def _build_base_insights(self) -> Dict[str, Any]:
        return {
            "license_costs": {},
            "key_business_areas": [],
            "competitive_advantages": [],
            "regulatory_concerns": [],
            "quantitative_profile": {},
            "topic_keyword_counts": {},
        }

    @staticmethod
    def _extract_thematic_sentences(text: str, keywords: List[str], limit: int = 5) -> List[str]:
        if not text:
            return []
        # Split on punctuation and line breaks to keep sentence extraction simple and robust.
        chunks = re.split(r"(?<=[\.\!\?])\s+|[\r\n]+", text)
        selected: List[str] = []
        seen: set = set()
        for sentence in chunks:
            cleaned = clean_text(sentence)
            if len(cleaned) < 20:
                continue
            if len(cleaned) > 260:
                cleaned = cleaned[:257] + "..."
            if cleaned in seen:
                continue
            lowered_sentence = cleaned.lower()
            if any(keyword.lower() in lowered_sentence for keyword in keywords):
                selected.append(cleaned)
                seen.add(cleaned)
            if len(selected) >= limit:
                break
        if not selected:
            # Fallback: return first contextual sentence if keyword scan misses due to noisy OCR text.
            for sentence in chunks:
                cleaned = clean_text(sentence)
                if len(cleaned) >= 30:
                    selected.append(cleaned[:260])
                    break
        return selected

    @staticmethod
    def _extract_quantitative_profile(text: str) -> Dict[str, Any]:
        amount_mentions = [clean_text(m.group(0)) for m in AMOUNT_RE.finditer(text)]
        percent_mentions = [clean_text(m.group(0)) for m in PERCENT_RE.finditer(text)]
        years = sorted({m.group(0) for m in YEAR_RE.finditer(text)})
        currency_codes = sorted({m.group(0).upper() for m in CURRENCY_CODE_RE.finditer(text)})
        return {
            "money_mentions_count": len(amount_mentions),
            "percent_mentions_count": len(percent_mentions),
            "year_mentions_count": len(years),
            "currency_codes": currency_codes[:10],
            "money_examples": amount_mentions[:8],
            "percent_examples": percent_mentions[:8],
            "year_examples": years[:8],
        }

    @staticmethod
    def _keyword_hit_counts(text: str) -> Dict[str, int]:
        lowered = text.lower()
        return {
            group: sum(lowered.count(keyword.lower()) for keyword in keywords)
            for group, keywords in INSIGHT_KEYWORDS.items()
        }

    def _build_section_insights(self, section_mapping: Dict[str, Any], content: Dict[str, Any]) -> Dict[str, Any]:
        insights = self._build_base_insights()
        text = safe_text(content.get("plain_text"))
        common_tag = safe_text(section_mapping.get("common_tag"))

        if text:
            insights["key_business_areas"] = self._extract_thematic_sentences(
                text,
                INSIGHT_KEYWORDS["business"],
                limit=5 if common_tag == "business_overview" else 3,
            )
            insights["competitive_advantages"] = self._extract_thematic_sentences(
                text,
                INSIGHT_KEYWORDS["advantage"],
                limit=4 if common_tag in {"business_overview", "mdna"} else 2,
            )
            insights["regulatory_concerns"] = self._extract_thematic_sentences(
                text,
                INSIGHT_KEYWORDS["regulation"],
                limit=4 if common_tag in {"risk_factors", "legal_proceedings"} else 2,
            )
            insights["quantitative_profile"] = self._extract_quantitative_profile(text)
            insights["topic_keyword_counts"] = self._keyword_hit_counts(text)
        return insights

    def _build_document_intelligence(self, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        coverage = Counter(
            safe_text(section.get("section_mapping", {}).get("common_tag")) for section in sections
        )
        total_tables = sum(1 for section in sections if section.get("content", {}).get("has_tables"))
        financial_sections = [
            safe_text(section.get("section_id"))
            for section in sections
            if section.get("content", {}).get("has_financial_data")
        ]

        currencies: Counter = Counter()
        risk_keyword_total = 0
        for section in sections:
            insights = section.get("extracted_insights", {})
            quant = insights.get("quantitative_profile", {})
            for code in quant.get("currency_codes", []):
                currencies[code] += 1
            topic_counts = insights.get("topic_keyword_counts", {})
            risk_keyword_total += int(topic_counts.get("regulation", 0))

        primary_tags = {"business_overview", "risk_factors", "mdna", "financials"}
        mapped_primary = len(primary_tags.intersection(set(coverage.keys())))
        mapping_completeness = round(mapped_primary / len(primary_tags), 4)

        return {
            "section_counts": dict(coverage),
            "total_sections": len(sections),
            "sections_with_tables": total_tables,
            "financial_signal_sections": financial_sections,
            "detected_currencies": dict(currencies),
            "risk_keyword_signal": risk_keyword_total,
            "core_mapping_completeness": mapping_completeness,
        }

    def to_schema_json(self) -> Dict[str, Any]:
        meta = self.extract_document_metadata()
        sections_info = self._get_sections_info()
        xbrl_summary = self._extract_sec_xbrl_summary()
        entity_profile = self._extract_entity_profile()

        sections: List[Dict[str, Any]] = []
        for item in sections_info:
            content = self.extract_section_content(item)
            section_payload = {
                "section_id": item["section_id"],
                "section_mapping": item["section_mapping"],
                "content": content,
                "extracted_insights": self._build_section_insights(item["section_mapping"], content),
            }
            sections.append(section_payload)

        if self._license_insights:
            preferred_tags = {"business_overview", "mdna", "financials"}
            target_section = None
            for section in sections:
                tag = section["section_mapping"].get("common_tag")
                if tag in preferred_tags:
                    target_section = section
                    break
            if target_section is None and sections:
                target_section = sections[0]
            if target_section is not None:
                target_section["extracted_insights"]["license_costs"] = self._license_insights

        total_tokens = sum(section["content"]["token_count"] for section in sections)
        document_intelligence = self._build_document_intelligence(sections)

        result = {
            "document_id": self._build_document_id(meta),
            "source_info": {
                "system": self.source_type,
                "document_type": meta.get("document_type"),
                "filing_date": meta.get("filing_date"),
                "period_end": meta.get("period_end"),
                "language": meta.get("language"),
            },
            "company": {
                "name": meta.get("company_name"),
                "identifier": meta.get("identifier"),
                "ticker": self.file_metadata.get("ticker"),
                "industry": self.file_metadata.get("industry"),
                "country": "US" if self.source_type == "SEC" else "KR",
            },
            "processing_info": {
                "ingestion_date": datetime.now(timezone.utc).date().isoformat(),
                "parser_version": self.parser_version,
                "total_tokens": total_tokens,
                "status": "parsed",
            },
            "document_metadata": meta,
            "entity_profile": entity_profile,
            "xbrl_summary": xbrl_summary,
            "document_intelligence": document_intelligence,
            "sections": sections,
        }
        return result

    def get_section_analysis_table(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        schema = self.to_schema_json()
        for section in schema.get("sections", []):
            rows.append(
                {
                    "order_index": section["section_mapping"]["order_index"],
                    "common_tag": section["section_mapping"]["common_tag"],
                    "source_label": section["section_mapping"]["sec_label"]
                    if self.source_type == "SEC"
                    else section["section_mapping"]["dart_label"],
                    "text_length": len(section["content"]["plain_text"]),
                    "token_count": section["content"]["token_count"],
                    "has_tables": section["content"]["has_tables"],
                    "has_financial_data": section["content"]["has_financial_data"],
                }
            )
        return rows
