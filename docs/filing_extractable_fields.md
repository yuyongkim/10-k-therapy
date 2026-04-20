# Filing Extractable Fields

This document summarizes what can be extracted from SEC/DART filing HTML/XML in this project and where each field should land in the unified schema.

## Extractable Data

| Category | Extractable fields | Source pattern | Current method | Target schema path |
|---|---|---|---|---|
| Document identity | `document_id`, `source`, `document_type`, `filing_date`, `period_end` | SEC item headers, DART metadata, filing JSON metadata | Rule-based parser | `document_id`, `source_info.*`, `document_metadata.*` |
| Company profile | `company_name`, `identifier(cik/corp_code)`, `ticker`, `industry`, `country` | Filing metadata + inline entity tags | Rule-based parser | `company.*`, `entity_profile.*` |
| Section map | normalized tags such as `business_overview`, `risk_factors`, `mdna`, `financials`, `legal_proceedings`, `governance` | SEC `Item n` headings, DART heading patterns | Rule-based mapping | `sections[].section_mapping.*` |
| Section content | raw HTML snippet, plain text, token estimate, table presence, financial signal flag | body block between adjacent headings | HTML chunk extraction | `sections[].content.*` |
| Business insights | key business areas, competitive advantages | sentence-level keyword hits | Rule-based sentence extraction | `sections[].extracted_insights.key_business_areas`, `sections[].extracted_insights.competitive_advantages` |
| Risk insights | regulation and litigation concerns | risk/legal keyword hits | Rule-based sentence extraction | `sections[].extracted_insights.regulatory_concerns` |
| Quantitative signals | money mentions, percent mentions, year mentions, currency codes | regex on section plain text | Pattern extraction | `sections[].extracted_insights.quantitative_profile.*` |
| Topic intensity | keyword hit counts by group | keyword frequency | Rule-based counting | `sections[].extracted_insights.topic_keyword_counts.*` |
| XBRL snapshot | key metrics and metric history (when tags exist) | inline XBRL tags and contexts | Tag/context parser | `xbrl_summary.*` |
| License candidates | note number, note title, relevance score, matched keywords/companies | Notes to financial statements text | note split + scoring filter | `license_candidates[]` |
| License agreements | parties, technology, industry, upfront payment, royalty, term, territory, confidence | candidate note content or Exhibit text | LLM extraction (Gemini/Ollama) | `agreements[]` |
| License cost summary | total annual cost, major licenses, confidence, source location | normalized agreements | deterministic aggregation | `agreement_summary.*` and `sections[].extracted_insights.license_costs` |
| Document intelligence | section count, table count, financial-signal sections, currency distribution, risk signal | all parsed sections | deterministic aggregation | `document_intelligence.*` |
| Provenance | parser version, run id, model/provider, input file paths | pipeline runtime context | pipeline metadata assembly | `processing_info.*`, `lineage.*` |

## What Is Already Strong

- Section segmentation and normalization are stable for SEC `Item` patterns and main DART section headings.
- Quantitative signal extraction works without LLM and scales to large local corpora.
- License summary injection into unified schema is already supported.

## What Needs Improvement

- Agreement evidence spans (exact quote offsets and section anchors) are not yet persisted end-to-end.
- Multi-currency normalization and FX-date alignment are not yet standardized.
- Party/entity canonicalization is heuristic and should be upgraded to dictionary or NER-based resolution.

## Recommended Next Build Steps

1. Add `agreement_id` and `source_anchor` (section id + note id + text span) in extraction output.
2. Add deterministic post-processing for currency normalization and annualization.
3. Add confidence decomposition: extraction confidence, parse confidence, and evidence coverage.
4. Add schema validation gate before writing final JSON outputs.

