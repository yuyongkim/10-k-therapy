from pathlib import Path
import tempfile

from parser.unified_disclosure_parser import (
    SEC10KParser,
    validate_schema_output,
)


SAMPLE_HTML = (
    Path("data")
    / "raw_filings"
    / "0000002098"
    / "10-K"
    / "0000950170-25-034843"
    / "primary_document.html"
)
SAMPLE_META = (
    Path("data")
    / "raw_filings"
    / "0000002098"
    / "10-K"
    / "0000950170-25-034843"
    / "filing_metadata.json"
)


def test_sec_schema_output_valid():
    assert SAMPLE_HTML.exists(), f"Missing sample HTML: {SAMPLE_HTML}"
    parser = SEC10KParser(str(SAMPLE_HTML), str(SAMPLE_META))
    result = parser.to_schema_json()

    assert validate_schema_output(result)
    assert result["source_info"]["system"] == "SEC"
    assert result["company"]["identifier"] == "0000002098"
    assert len(result["sections"]) >= 6
    assert "xbrl_summary" in result
    assert "document_intelligence" in result
    assert "entity_profile" in result
    assert isinstance(result["xbrl_summary"].get("key_metrics", {}), dict)
    assert isinstance(result["xbrl_summary"].get("metric_history", {}), dict)
    assert isinstance(result["xbrl_summary"].get("context_summary", {}), dict)
    assert any(
        section["section_mapping"]["common_tag"] == "business_overview"
        for section in result["sections"]
    )


def test_license_integration_with_existing_shape():
    parser = SEC10KParser(str(SAMPLE_HTML), str(SAMPLE_META))
    parser.integrate_license_analysis(
        {
            "license_costs": {
                "total_annual_cost": 15000000,
                "currency": "USD",
                "major_licenses": [
                    {
                        "licensor": "Sample Licensor",
                        "cost": 8000000,
                        "type": "patent_license",
                        "contract_period": "2023-2027",
                    }
                ],
                "analysis_confidence": 0.92,
                "source_location": "Item 1, Page 15",
            }
        }
    )
    result = parser.to_schema_json()
    assert validate_schema_output(result)

    enriched_sections = [
        section
        for section in result["sections"]
        if section["extracted_insights"].get("license_costs")
    ]
    assert len(enriched_sections) >= 1
    assert enriched_sections[0]["extracted_insights"]["license_costs"]["currency"] == "USD"


def test_license_integration_with_extractor_list():
    parser = SEC10KParser(str(SAMPLE_HTML), str(SAMPLE_META))
    parser.integrate_license_analysis(
        [
            {
                "source_note": {"note_number": "8"},
                "extraction": {
                    "agreements": [
                        {
                            "parties": {"licensor": {"name": "Company A"}},
                            "technology": {"category": "patent"},
                            "financial_terms": {
                                "upfront_payment": {"amount": "1200000", "currency": "USD"}
                            },
                            "contract_terms": {"term": {"years": 4}},
                            "metadata": {"confidence_score": 0.8},
                        }
                    ]
                },
            }
        ]
    )
    result = parser.to_schema_json()
    assert validate_schema_output(result)
    section = next(
        s for s in result["sections"] if s["extracted_insights"].get("license_costs")
    )
    costs = section["extracted_insights"]["license_costs"]
    assert costs["currency"] == "USD"
    assert costs["total_annual_cost"] == 300000.0


def test_sec_heading_fallback_without_item_ids():
    html = """
    <html><body>
      <h2>Item 1. Business</h2>
      <p>The business segment includes cloud services and devices.</p>
      <h2>Item 1A. Risk Factors</h2>
      <p>Regulatory risk and market volatility may materially affect results.</p>
      <h2>Item 7. Management's Discussion and Analysis</h2>
      <p>Revenue increased 12% to USD 1250000 in 2025.</p>
    </body></html>
    """
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "sec.html"
        html_path.write_text(html, encoding="utf-8")
        parser = SEC10KParser(str(html_path), metadata_path=None)
        result = parser.to_schema_json()

    assert validate_schema_output(result)
    tags = [section["section_mapping"]["common_tag"] for section in result["sections"]]
    assert "business_overview" in tags
    assert "risk_factors" in tags
    mdna_section = next(
        section for section in result["sections"] if section["section_mapping"]["common_tag"] == "mdna"
    )
    quant = mdna_section["extracted_insights"].get("quantitative_profile", {})
    assert quant.get("money_mentions_count", 0) >= 1
