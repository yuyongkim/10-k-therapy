"""SEC 10-K parser implementation."""

import re
from collections import Counter
from typing import Any, Dict, List, Optional

from bs4 import Tag

from .base_parser import DocumentParser
from .constants import (
    COMMON_TO_DART_LABEL,
    COMMON_TO_SEC_LABEL,
    ITEM_CODE_RE,
    SEC_TO_COMMON_TAG,
)
from .utils import clean_text, safe_text


class SEC10KParser(DocumentParser):
    def __init__(self, html_path: str, metadata_path: Optional[str] = None):
        super().__init__(html_path=html_path, source_type="SEC", metadata_path=metadata_path)

    def _parse_item_code(self, text: str, element_id: str = "") -> Optional[str]:
        from_id = re.match(r"item_(\d{1,2}[a-c]?)", safe_text(element_id).lower())
        if from_id:
            return from_id.group(1).upper()
        match = ITEM_CODE_RE.search(text)
        if match:
            return match.group(1).upper()
        return None

    @staticmethod
    def _is_toc_context(tag: Tag) -> bool:
        # Many SEC filings include duplicate Item headings inside TOC links/tables.
        for ancestor in [tag, *list(tag.parents)[:5]]:
            identifier = safe_text(getattr(ancestor, "attrs", {}).get("id"))
            classes = " ".join(getattr(ancestor, "attrs", {}).get("class", []))
            marker = f"{identifier} {classes}".lower()
            if "toc" in marker or "tableofcontents" in marker:
                return True
        if tag.find_parent("table") is not None:
            return True
        return False

    def identify_sections(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        allowed_names = {"h1", "h2", "h3", "h4", "div", "p", "span", "b", "strong"}

        for position, tag in enumerate(self.soup.find_all(True)):
            if tag.name.lower() not in allowed_names and not tag.get("id"):
                continue
            raw_label = clean_text(tag.get_text(" ", strip=True))
            if len(raw_label) < 5 or len(raw_label) > 180:
                continue
            tag_id = safe_text(tag.get("id"))
            item_code = self._parse_item_code(raw_label, tag_id)
            if not item_code:
                continue

            score = 0
            if tag_id.lower().startswith("item_"):
                score += 4
            if tag.name.lower() in {"h1", "h2", "h3", "h4"}:
                score += 2
            if len(raw_label) >= 12:
                score += 1
            if not self._is_toc_context(tag):
                score += 2
            else:
                score -= 2

            candidates.append(
                {
                    "tag": tag,
                    "item_code": item_code,
                    "raw_label": raw_label,
                    "score": score,
                    "position": position,
                }
            )

        chosen_by_code: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            code = candidate["item_code"]
            previous = chosen_by_code.get(code)
            if previous is None:
                chosen_by_code[code] = candidate
                continue
            # Higher quality first; later position breaks ties to avoid TOC duplicates.
            previous_key = (previous.get("score", 0), previous.get("position", 0))
            current_key = (candidate.get("score", 0), candidate.get("position", 0))
            if current_key > previous_key:
                chosen_by_code[code] = candidate

        ordered_headings = sorted(chosen_by_code.values(), key=lambda x: x.get("position", 0))
        if not ordered_headings:
            body = self.soup.body or self.soup
            return [
                {
                    "section_id": "other_disclosures",
                    "raw_label": "SEC Document Body",
                    "section_mapping": {
                        "common_tag": "other_disclosures",
                        "sec_label": COMMON_TO_SEC_LABEL["other_disclosures"],
                        "dart_label": COMMON_TO_DART_LABEL["other_disclosures"],
                        "order_index": 1,
                    },
                    "_heading_tag": body if isinstance(body, Tag) else None,
                    "_next_heading_tag": None,
                }
            ]

        output_sections: List[Dict[str, Any]] = []
        used_section_ids: Counter = Counter()

        for idx, heading in enumerate(ordered_headings):
            next_tag = ordered_headings[idx + 1]["tag"] if idx + 1 < len(ordered_headings) else None
            common_tag = SEC_TO_COMMON_TAG.get(heading["item_code"], "other_disclosures")
            used_section_ids[common_tag] += 1
            suffix = "" if used_section_ids[common_tag] == 1 else f"_{used_section_ids[common_tag]}"
            section_id = f"{common_tag}{suffix}"

            output_sections.append(
                {
                    "section_id": section_id,
                    "raw_label": heading["raw_label"],
                    "section_mapping": {
                        "common_tag": common_tag,
                        "sec_label": heading["raw_label"],
                        "dart_label": COMMON_TO_DART_LABEL.get(common_tag, COMMON_TO_DART_LABEL["other_disclosures"]),
                        "order_index": idx + 1,
                    },
                    "_heading_tag": heading["tag"],
                    "_next_heading_tag": next_tag,
                }
            )

        return output_sections
