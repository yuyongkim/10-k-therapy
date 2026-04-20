"""DART disclosure parser implementation."""

import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import Tag

from .base_parser import DocumentParser
from .constants import (
    COMMON_TO_SEC_LABEL,
    DART_HEADING_PATTERNS,
)
from .utils import clean_text, tag_attr


class DARTParser(DocumentParser):
    def __init__(self, html_path: str, metadata_path: Optional[str] = None):
        super().__init__(html_path=html_path, source_type="DART", metadata_path=metadata_path)

    @staticmethod
    def _normalized_heading_forms(raw_label: str, eng_label: str) -> Tuple[str, str]:
        merged = clean_text(f"{raw_label} {eng_label}".strip())
        compact = re.sub(r"\s+", "", merged).lower()
        return merged, compact

    def _match_common_tag(self, raw_label: str, eng_label: str) -> Optional[str]:
        merged, compact = self._normalized_heading_forms(raw_label, eng_label)
        best_tag: Optional[str] = None
        best_score = 0

        for common_tag, patterns in DART_HEADING_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, merged, flags=re.IGNORECASE):
                    score += 2
                elif re.search(pattern, compact, flags=re.IGNORECASE):
                    score += 1
            if score > best_score:
                best_tag = common_tag
                best_score = score
        return best_tag

    @staticmethod
    def _heading_quality_score(tag: Tag, raw_label: str, eng_label: str) -> int:
        score = 0
        atoc = tag_attr(tag, "ATOC").upper()
        if atoc == "Y":
            score += 2
        if tag.name.lower() == "cover-title":
            score += 2
        if re.match(r"^[IVXLC]+\.", raw_label):
            score += 4
        if re.match(r"^[IVXLC]+\.", eng_label):
            score += 3
        if re.match(r"^\d+\.", raw_label):
            score += 1
        if 4 <= len(raw_label) <= 120:
            score += 1
        return score

    def identify_sections(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        allowed_tag_names = {"title", "cover-title", "h1", "h2", "h3", "h4"}

        for position, tag in enumerate(self.soup.find_all(True)):
            if tag.name.lower() not in allowed_tag_names:
                continue

            atoc = tag_attr(tag, "ATOC").upper()
            if tag.name.lower() == "title" and atoc and atoc != "Y":
                continue

            raw_label = clean_text(tag.get_text(" ", strip=True))
            eng_label = clean_text(tag_attr(tag, "ENG"))
            merged_label, _ = self._normalized_heading_forms(raw_label, eng_label)
            if len(merged_label) < 4 or len(merged_label) > 180:
                continue

            matched_common = self._match_common_tag(raw_label, eng_label)
            if not matched_common:
                continue

            score = self._heading_quality_score(tag, raw_label, eng_label)
            candidates.append(
                {
                    "tag": tag,
                    "common_tag": matched_common,
                    "raw_label": raw_label,
                    "eng_label": eng_label,
                    "position": position,
                    "score": score,
                }
            )

        selected_by_common: Dict[str, Dict[str, Any]] = {}
        for item in candidates:
            common = item["common_tag"]
            prev = selected_by_common.get(common)
            if prev is None:
                selected_by_common[common] = item
                continue
            prev_key = (prev.get("score", 0), -prev.get("position", 0))
            curr_key = (item.get("score", 0), -item.get("position", 0))
            if curr_key > prev_key:
                selected_by_common[common] = item

        output_sections: List[Dict[str, Any]] = []
        ordered_candidates = sorted(selected_by_common.values(), key=lambda x: x.get("position", 0))
        for idx, item in enumerate(ordered_candidates):
            next_tag = ordered_candidates[idx + 1]["tag"] if idx + 1 < len(ordered_candidates) else None
            output_sections.append(
                {
                    "section_id": item["common_tag"],
                    "raw_label": item["raw_label"],
                    "section_mapping": {
                        "common_tag": item["common_tag"],
                        "sec_label": COMMON_TO_SEC_LABEL.get(item["common_tag"], COMMON_TO_SEC_LABEL["other_disclosures"]),
                        "dart_label": item["raw_label"],
                        "dart_eng_label": item.get("eng_label"),
                        "order_index": idx + 1,
                    },
                    "_heading_tag": item["tag"],
                    "_next_heading_tag": next_tag,
                }
            )

        if not output_sections:
            # Fallback for files that do not include identifiable DART section headings.
            body = self.soup.body or self.soup
            output_sections.append(
                {
                    "section_id": "other_disclosures",
                    "raw_label": "DART Document Body",
                    "section_mapping": {
                        "common_tag": "other_disclosures",
                        "sec_label": COMMON_TO_SEC_LABEL["other_disclosures"],
                        "dart_label": "\ubcf8\ubb38",
                        "order_index": 1,
                    },
                    "_heading_tag": body if isinstance(body, Tag) else None,
                    "_next_heading_tag": None,
                }
            )
        return output_sections
