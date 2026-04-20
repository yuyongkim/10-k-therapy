import tempfile
from pathlib import Path

from crawler.dart_crawler import OpenDartCrawler
from parser.unified_disclosure_parser import DARTParser, validate_schema_output


def test_parse_corp_code_xml():
    xml_bytes = b"""
    <result>
      <list>
        <corp_code>00126380</corp_code>
        <corp_name>\xec\x82\xbc\xec\x84\xb1\xec\xa0\x84\xec\x9e\x90</corp_name>
        <stock_code>005930</stock_code>
        <modify_date>20250101</modify_date>
      </list>
      <list>
        <corp_code>00164779</corp_code>
        <corp_name>LG\xed\x99\x94\xed\x95\x99</corp_name>
        <stock_code>051910</stock_code>
        <modify_date>20250101</modify_date>
      </list>
    </result>
    """
    rows = OpenDartCrawler.parse_corp_code_xml(xml_bytes)
    assert len(rows) == 2
    assert rows[0]["corp_code"] == "00126380"
    assert rows[0]["stock_code"] == "005930"


def test_dart_parser_identifies_sections_from_html_headings():
    html = """
    <html><body>
      <h2>II. Business Description</h2><p>Business overview body</p>
      <h2>Risk Management and Derivatives Transactions</h2><p>Risk details</p>
      <h2>III. Financial Matters</h2><p>Revenue KRW 1000</p>
      <h2>Consolidated Financial Statements</h2><table><tr><td>Assets</td><td>5000</td></tr></table>
      <h2>VI. Matters Related to Corporate Bodies Including the Board of Directors, etc.</h2><p>Governance body</p>
    </body></html>
    """
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "doc.html"
        meta_path = Path(td) / "meta.json"
        html_path.write_text(html, encoding="utf-8")
        meta_path.write_text(
            '{"filing":{"report_nm":"Quarterly Report (2024.12)","rcept_dt":"20250307","corp_name":"Test Corp","corp_code":"00126380"}}',
            encoding="utf-8",
        )
        parser = DARTParser(str(html_path), str(meta_path))
        result = parser.to_schema_json()

    assert validate_schema_output(result)
    tags = [s["section_mapping"]["common_tag"] for s in result["sections"]]
    assert "business_overview" in tags
    assert "risk_factors" in tags
    assert "mdna" in tags or "financials" in tags
    assert "governance" in tags
    assert result["source_info"]["system"] == "DART"
    assert result["company"]["country"] == "KR"


def test_dart_parser_fallback_section():
    html = "<html><body><p>Body only without identifiable sections</p></body></html>"
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "doc.html"
        html_path.write_text(html, encoding="utf-8")
        parser = DARTParser(str(html_path), metadata_path=None)
        result = parser.to_schema_json()

    assert validate_schema_output(result)
    assert len(result["sections"]) == 1
    assert result["sections"][0]["section_mapping"]["common_tag"] == "other_disclosures"


def test_dart_parser_malformed_xml_with_eng_titles():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <BODY>
        <TITLE ATOC="Y" ENG="II. Business Description">II. Business Description</TITLE>
        <P>Business overview body</P>
        <TITLE ATOC="Y" ENG="III. Financial Matters">III. Financial Matters</TITLE>
        <P>Financial body</P>
        <TITLE ATOC="Y" ENG="VI. Matters Related to Corporate Bodies Including the Board of Directors, etc.">
          VI. Corporate Bodies
        </TITLE>
        <TD>malformed
      </BODY>
    </DOCUMENT>
    """
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "doc.xml"
        html_path.write_text(xml, encoding="utf-8")
        parser = DARTParser(str(html_path), metadata_path=None)
        result = parser.to_schema_json()

    assert validate_schema_output(result)
    tags = [s["section_mapping"]["common_tag"] for s in result["sections"]]
    assert "business_overview" in tags
    assert "mdna" in tags or "financials" in tags
    assert "governance" in tags
    assert any("dart_eng_label" in s["section_mapping"] for s in result["sections"])
