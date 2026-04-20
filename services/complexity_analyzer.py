"""
Text Complexity Analyzer for AI Model Routing

Scores contract text complexity on a 0-10 scale:
  0-3  → qwen_only (local, free)
  4-6  → qwen_with_fallback (try Qwen, fallback to Claude if low confidence)
  7-10 → claude_direct (complex, send to Claude directly)
"""

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ComplexityScore:
    total_score: int
    length_factor: int
    legal_density: int
    numeric_complexity: int
    ambiguity_factor: int

    def get_routing_decision(self) -> str:
        if self.total_score <= 3:
            return "qwen_only"
        elif self.total_score <= 6:
            return "qwen_with_fallback"
        else:
            return "claude_direct"


class ComplexityAnalyzer:
    """Analyzes contract text complexity for AI routing decisions.
    Supports both English and Korean legal text."""

    # English legal keywords
    LEGAL_KEYWORDS_EN: List[str] = [
        "pursuant to", "notwithstanding", "hereinafter", "indemnif",
        "force majeure", "severability", "arbitration", "governing law",
        "intellectual property", "sublicense", "sublicens", "termination",
        "representations and warranties", "confidential", "trade secret",
        "infringement", "enjoin", "injunctive", "liquidated damages",
        "consequential", "limitation of liability", "irrevocable",
        "non-exclusive", "exclusive license", "perpetual", "royalty-free",
        "milestone", "upfront payment", "lump sum", "running royalty",
        "minimum annual", "net sales", "gross revenue", "fair market value",
        "change of control", "assignment", "breach", "cure period",
        "material adverse", "regulatory approval", "fda approval",
        "patent", "copyright", "trademark", "know-how",
    ]

    # Korean legal/IP keywords for DART filings
    LEGAL_KEYWORDS_KR: List[str] = [
        # 라이선스 / IP 핵심 용어
        "라이선스", "라이센스", "실시권", "사용권", "특허권",
        "기술도입", "기술이전", "기술제휴", "기술계약",
        "로열티", "사용료", "기술료", "실시료", "경상기술료",
        "선급금", "착수금", "계약금", "일시금", "정액기술료",
        # 계약 조건
        "독점", "비독점", "전용실시권", "통상실시권",
        "계약기간", "갱신", "해지", "종료", "유효기간",
        "계약금액", "대가", "지급조건",
        # IP 유형
        "특허", "노하우", "영업비밀", "상표권", "저작권",
        "지식재산", "지적재산", "산업재산권",
        # 법률 용어
        "손해배상", "면책", "비밀유지", "기밀유지",
        "준거법", "중재", "분쟁해결", "관할",
        "양도", "재실시", "하도급",
        # 산업/규제
        "의약품", "신약", "임상", "식약처", "허가",
        "촉매", "공정기술", "제조기술",
        "반도체", "소프트웨어",
    ]

    # Combined for backward compatibility
    LEGAL_KEYWORDS: List[str] = LEGAL_KEYWORDS_EN + LEGAL_KEYWORDS_KR

    AMBIGUITY_PATTERNS: List[str] = [
        # English
        r"subject to\b", r"provided that\b", r"except as\b",
        r"notwithstanding\b", r"in the event\b", r"to the extent\b",
        r"may\s+(?:not\s+)?be\b", r"shall\s+(?:not\s+)?be\b",
        r"unless\b", r"however\b", r"contingent\b", r"conditional\b",
        r"at the discretion\b", r"reasonable\b", r"commercially reasonable\b",
        r"best efforts\b", r"good faith\b", r"mutually agree\b",
        # Korean ambiguity/conditional patterns
        r"단[,\s]", r"다만[,\s]", r"그러나\b", r"그럼에도\b",
        r"경우에\s*한하여", r"범위\s*내에서", r"조건으로",
        r"합리적[인\s]", r"성실[히하]", r"상호\s*합의",
        r"재량[에으]", r"선의[로의]",
    ]

    NUMERIC_PATTERNS: List[str] = [
        # English
        r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand))?",
        r"\d+(?:\.\d+)?\s*%",
        r"\d{1,2}/\d{1,2}/\d{2,4}",
        r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s*\d{4}",
        r"\d+(?:\.\d+)?\s*(?:years?|months?|days?)",
        r"(?:section|article|clause)\s+\d+(?:\.\d+)*",
        # Korean numeric patterns
        r"[\d,]+(?:\.\d+)?\s*(?:원|백만원|억원|천만원|만원)",
        r"[\d,]+(?:\.\d+)?\s*(?:달러|USD|EUR|JPY|유로|엔)",
        r"\d{4}[년.]\s*\d{1,2}[월.]\s*\d{1,2}[일.]?",  # Korean dates: 2024년 3월 15일
        r"\d+(?:\.\d+)?\s*(?:년간|년|개월|일간)",  # Duration: 5년간, 3개월
        r"제?\s*\d+\s*[조항호]",  # Article references: 제3조, 제5항
        r"매출[액의]\s*[\d.]+\s*%",  # Revenue-based royalty
    ]

    def analyze_text(self, text: str) -> ComplexityScore:
        """Analyze text and return complexity score."""
        length_factor = self._score_length(text)
        legal_density = self._score_legal_terms(text)
        numeric_complexity = self._score_numeric(text)
        ambiguity_factor = self._score_ambiguity(text)

        total = length_factor + legal_density + numeric_complexity + ambiguity_factor

        return ComplexityScore(
            total_score=min(10, total),
            length_factor=length_factor,
            legal_density=legal_density,
            numeric_complexity=numeric_complexity,
            ambiguity_factor=ambiguity_factor,
        )

    def _score_length(self, text: str) -> int:
        length = len(text)
        if length < 2000:
            return 0
        elif length < 5000:
            return 1
        else:
            return 2

    def _detect_language(self, text: str) -> str:
        """Detect if text is primarily Korean or English."""
        korean_chars = sum(1 for c in text[:500] if '\uac00' <= c <= '\ud7a3')
        return "ko" if korean_chars > len(text[:500]) * 0.1 else "en"

    def _score_legal_terms(self, text: str) -> int:
        text_lower = text.lower()
        lang = self._detect_language(text)

        # Use language-appropriate keyword list for primary scoring
        if lang == "ko":
            count = sum(1 for term in self.LEGAL_KEYWORDS_KR if term in text_lower)
            # Also check English terms (mixed-language docs are common in Korean filings)
            count += sum(1 for term in self.LEGAL_KEYWORDS_EN if term in text_lower)
        else:
            count = sum(1 for term in self.LEGAL_KEYWORDS_EN if term in text_lower)

        # Density per 1000 chars (Korean text is denser, so lower threshold)
        chars = max(len(text), 1)
        density = count / (chars / 1000)

        # Korean text carries more information per character
        if lang == "ko":
            if density < 1:
                return 0
            elif density < 3:
                return 1
            elif density < 6:
                return 2
            else:
                return 3
        else:
            if density < 2:
                return 0
            elif density < 5:
                return 1
            elif density < 10:
                return 2
            else:
                return 3

    def _score_numeric(self, text: str) -> int:
        text_lower = text.lower()
        count = 0
        for pattern in self.NUMERIC_PATTERNS:
            count += len(re.findall(pattern, text_lower, re.IGNORECASE))

        if count < 3:
            return 0
        elif count < 8:
            return 1
        elif count < 15:
            return 2
        else:
            return 3

    def _score_ambiguity(self, text: str) -> int:
        text_lower = text.lower()
        count = 0
        for pattern in self.AMBIGUITY_PATTERNS:
            count += len(re.findall(pattern, text_lower))

        if count < 3:
            return 0
        elif count < 8:
            return 1
        else:
            return 2
