"""Constants, mappings, and regex patterns for the unified disclosure parser."""

import re

PARSER_VERSION = "v1.1.0"

SEC_TO_COMMON_TAG = {
    "1": "business_overview",
    "1A": "risk_factors",
    "1B": "other_disclosures",
    "1C": "other_disclosures",
    "2": "other_disclosures",
    "3": "legal_proceedings",
    "4": "other_disclosures",
    "5": "major_events",
    "6": "other_disclosures",
    "7": "mdna",
    "7A": "mdna",
    "8": "financials",
    "9": "other_disclosures",
    "9A": "other_disclosures",
    "9B": "other_disclosures",
    "9C": "other_disclosures",
    "10": "governance",
    "11": "governance",
    "12": "governance",
    "13": "governance",
    "14": "governance",
    "15": "financials",
    "16": "other_disclosures",
}

COMMON_TO_SEC_LABEL = {
    "business_overview": "Item 1. Business",
    "risk_factors": "Item 1A. Risk Factors",
    "mdna": "Item 7. Management Discussion and Analysis",
    "financials": "Item 8. Financial Statements",
    "legal_proceedings": "Item 3. Legal Proceedings",
    "governance": "Item 10/11. Governance",
    "major_events": "Item 5. Market and Related Matters",
    "other_disclosures": "Other SEC Disclosures",
}

COMMON_TO_DART_LABEL = {
    "business_overview": "\u2161. \uc0ac\uc5c5\uc758 \ub0b4\uc6a9",
    "risk_factors": "\ud22c\uc790\uc704\ud5d8\uc694\uc18c",
    "mdna": "\uc7ac\ubb34\uc5d0 \uad00\ud55c \uc0ac\ud56d (\uacbd\uc601\uc9c4 \ubd84\uc11d)",
    "financials": "\uc7ac\ubb34\uc81c\ud45c",
    "legal_proceedings": "\uc18c\uc1a1 \ub610\ub294 \ubc95\uc801 \uc808\ucc28",
    "governance": "\uc784\uc6d0 \ud604\ud669 /\uc9c0\ubc30\uad6c\uc870",
    "major_events": "\uc8fc\uc694 \uacc4\uc57d \ubc0f \uc774\ubca4\ud2b8",
    "other_disclosures": "\uae30\ud0c0 \uacf5\uc2dc\uc0ac\ud56d",
}

DART_HEADING_PATTERNS = {
    "business_overview": [
        r"\b(?:I|II)\.?\s*\uD68C\uC0AC\uC758\s*\uAC1C\uC694\b",
        r"\bII\.?\s*\uC0AC\uC5C5\uC758\s*\uB0B4\uC6A9\b",
        r"\bbusiness\s+description\b",
        r"\bbusiness\s+overview\b",
        r"\bcompany\s+overview\b",
    ],
    "risk_factors": [
        r"\uD22C\uC790\uC704\uD5D8\uC694\uC18C",
        r"\uC704\uD5D8\uAD00\uB9AC",
        r"\uC6B0\uBC1C\uBD80\uCC44",
        r"\uC81C\uC7AC",
        r"\binvestor\s+protection\b",
        r"\brisk\s+management\b",
        r"\bcontingent\s+liabilit",
        r"\bsanction",
    ],
    "mdna": [
        r"\uACBD\uC601\uC758?\s*\uB0B4\uC6A9\s*\uBC0F\s*\uC7AC\uBB34",
        r"\uC7AC\uBB34\uC5D0\s*\uAD00\uD55C\s*\uC0AC\uD56D",
        r"\bfinancial\s+matters\b",
        r"\bmanagement\s+discussion",
    ],
    "financials": [
        r"\uC7AC\uBB34\uC81C\uD45C",
        r"\uC5F0\uACB0\uC7AC\uBB34\uC81C\uD45C",
        r"\uC7AC\uBB34\uC0C1\uD0DC\uD45C",
        r"\uC190\uC775\uACC4\uC0B0\uC11C",
        r"\uD3EC\uAD04\uC190\uC775\uACC4\uC0B0\uC11C",
        r"\uD604\uAE08\uD750\uB984\uD45C",
        r"\bfinancial\s+statement",
        r"\bconsolidated\s+financial\s+statement",
        r"\bsummary\s+of\s+financial\s+information\b",
    ],
    "legal_proceedings": [
        r"\uC18C\uC1A1",
        r"\uBC95\uC801\s*\uC808\uCC28",
        r"\blegal\s+proceeding",
        r"\blitigation",
        r"\bcontingent\s+liabilit",
    ],
    "governance": [
        r"\uC784\uC6D0\s*\uD604\uD669",
        r"\uC9C0\uBC30\uAD6C\uC870",
        r"\uC774\uC0AC\uD68C",
        r"\uC8FC\uC8FC",
        r"\uAC10\uC0AC\uC81C\uB3C4",
        r"\uB0B4\uBD80\uD1B5\uC81C",
        r"\bboard\b",
        r"\bdirector",
        r"\bexecutive",
        r"\bshareholder",
        r"\bcorporate\s+bodies\b",
    ],
    "major_events": [
        r"\uC8FC\uC694\s*\uACC4\uC57D",
        r"\uC5F0\uAD6C\uAC1C\uBC1C",
        r"\uB300\uC8FC\uC8FC\s*\uB4F1\uACFC\uC758\s*\uAC70\uB798",
        r"M&A",
        r"CB|BW",
        r"\bmajor\s+contract",
        r"\bresearch\s+and\s+development",
        r"\btransactions?\s+with\s+major\s+shareholders?\b",
    ],
}

ITEM_CODE_RE = re.compile(r"\bItem\s*(\d{1,2}[A-C]?)\b", re.IGNORECASE)
CURRENCY_RE = re.compile(r"\b(USD|KRW|EUR|JPY|GBP)\b", re.IGNORECASE)
FINANCIAL_SIGNAL_RE = re.compile(
    r"(\$|USD|KRW|million|billion|revenue|income|loss|asset|liabilit|cash flow|royalt)",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
AMOUNT_RE = re.compile(
    r"(?:[$\u20ac\u00a3\u00a5]|USD|KRW|EUR|JPY|GBP)\s*-?\d[\d,]*(?:\.\d+)?(?:\s*(?:thousand|million|billion|mn|bn|\uc5b5\uc6d0|\ubc31\ub9cc\uc6d0))?",
    re.IGNORECASE,
)
CURRENCY_CODE_RE = re.compile(r"\b(?:USD|KRW|EUR|JPY|GBP|CNY|HKD)\b", re.IGNORECASE)

INSIGHT_KEYWORDS = {
    "business": [
        "business segment",
        "segment",
        "product",
        "service",
        "customer",
        "market",
        "platform",
        "\uc0ac\uc5c5",
        "\uc81c\ud488",
        "\uc11c\ube44\uc2a4",
        "\uace0\uac1d",
        "\uc2dc\uc7a5",
        "\uc0ac\uc5c5\ubd80",
    ],
    "advantage": [
        "competitive advantage",
        "moat",
        "leading",
        "proprietary",
        "technology",
        "patent",
        "brand",
        "cost leadership",
        "\uacbd\uc7c1\uc6b0\uc704",
        "\ucc28\ubcc4\ud654",
        "\uae30\uc220\ub825",
        "\ube0c\ub79c\ub4dc",
        "\ud2b9\ud5c8",
        "\uc9c4\uc785\uc7a5\ubcbd",
    ],
    "regulation": [
        "regulation",
        "compliance",
        "regulatory",
        "legal",
        "litigation",
        "investigation",
        "sanction",
        "environmental",
        "SEC",
        "DART",
        "\uaddc\uc81c",
        "\uc900\uc218",
        "\ubc95\ub960",
        "\uc18c\uc1a1",
        "\uac10\ub3c5",
        "\ud658\uacbd",
    ],
}

SEC_KEY_METRIC_CONCEPTS = {
    "revenue": ["us-gaap:Revenues", "us-gaap:SalesRevenueNet"],
    "gross_profit": ["us-gaap:GrossProfit"],
    "operating_income": ["us-gaap:OperatingIncomeLoss"],
    "net_income": ["us-gaap:NetIncomeLoss"],
    "total_assets": ["us-gaap:Assets"],
    "total_liabilities": ["us-gaap:Liabilities"],
    "shareholders_equity": [
        "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "us-gaap:StockholdersEquity",
    ],
    "cash_and_equivalents": ["us-gaap:CashAndCashEquivalentsAtCarryingValue"],
    "eps_diluted": ["us-gaap:EarningsPerShareDiluted"],
    "weighted_avg_shares_diluted": ["us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"],
}
