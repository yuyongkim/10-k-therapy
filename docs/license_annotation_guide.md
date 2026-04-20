# License Annotation Guide

Use this guide to build a paper-grade gold set for SEC/DART license extraction evaluation.

## Goal

- Define a consistent unit of annotation across SEC and DART filings.
- Produce a gold set that supports document-level, agreement-level, and field-level evaluation.
- Keep annotation rules simple enough for two-pass review and inter-annotator agreement checks.

## Recommended Gold Set Scope

- Initial pilot: 50 documents
- First publishable set: 200 documents
- Stronger benchmark: 500 documents
- Source mix:
  - SEC 10-K / 10-Q filings with likely license notes
  - DART annual / quarterly / semiannual reports with contract or IP sections
- Balance:
  - positive documents with at least one true license agreement
  - hard negatives with contract-like but non-license text
  - sector diversity across pharma, software, semiconductor, energy, manufacturing, finance

## Unit Of Annotation

- A document is the filing-level unit.
- An agreement is the primary extraction unit.
- One document may contain zero, one, or multiple agreements.
- Each agreement should include anchor fields that let it be matched back to model output.

## Positive Definition

Annotate an agreement as positive only when the filing text supports a real license-like grant or economically meaningful use right tied to IP, technology, brand, data, software, content, process know-how, or a comparable intangible asset.

Examples that usually count:

- patent license
- software license
- trademark or brand license
- technology transfer with licensing terms
- franchise agreement with explicit brand/IP usage rights
- royalty-bearing commercialization rights

Examples that usually do not count:

- ordinary supply agreement
- lease with no IP grant
- generic service contract
- debt facility or financing agreement
- litigation settlement without a continuing license grant
- warranty language, reimbursement policy, or product recall text

## Borderline Cases

- If the text only implies permission to use technology but does not describe a contract or grant, mark `agreement_present=false`.
- If the filing references a license program at high level but gives no specific agreement, keep the document positive only when the disclosure clearly indicates an active licensing arrangement.
- If multiple amendments refer to the same commercial arrangement, annotate one agreement unless the filing presents clearly distinct licensed assets or counterparties.

## Gold Record Format

Store one JSON object per line in a `.jsonl` file.

```json
{
  "document_id": "SEC_0000002098_2025_10K",
  "source_system": "SEC",
  "agreement_present": true,
  "agreements": [
    {
      "agreement_id": "optional-local-id",
      "source_section_id": "sec_item_8_note_12",
      "source_note_number": "12",
      "licensor_name": "Company A",
      "licensee_name": "Company B",
      "technology_name": "oncology antibody platform",
      "technology_category": "patent_license",
      "industry": "Pharmaceutical",
      "upfront_amount": 25000000,
      "currency": "USD",
      "royalty_rate": 7.5,
      "royalty_unit": "percent_net_sales",
      "term_years": 10,
      "territory": ["US", "EU"],
      "evidence_text": "On March 4, 2025, the Company entered into..."
    }
  ]
}
```

## Required Fields

- `document_id`: must match the pipeline output document id.
- `agreement_present`: `true` if at least one valid agreement exists.
- `agreements`: empty list when the document is negative.

## Strongly Recommended Agreement Fields

- `source_note_number` or `source_section_id`
- `licensor_name`
- `licensee_name`
- `technology_category`
- `evidence_text`

These anchors make agreement-level matching much more reliable than amount-only matching.

## Field Instructions

- `agreement_id`: optional local label for annotation management, not a legal identifier.
- `source_section_id`: preferred when the parser gives a stable section id.
- `source_note_number`: use the note number if the agreement is disclosed in notes.
- `licensor_name` / `licensee_name`: canonical entity names when possible. If the filing only says `the Company`, keep that literal string.
- `technology_name`: short free text name of the licensed asset.
- `technology_category`: use a compact controlled vocabulary. Recommended values:
  - `patent_license`
  - `software_license`
  - `trademark_license`
  - `content_license`
  - `data_license`
  - `franchise_license`
  - `technology_transfer`
  - `other_license`
- `industry`: keep the project's existing sector wording where possible.
- `upfront_amount`: numeric only. Convert commas and text formatting away.
- `currency`: ISO-like code such as `USD`, `KRW`, `EUR`.
- `royalty_rate`: numeric only.
- `royalty_unit`: short normalized label such as `percent_net_sales`, `percent_revenue`, `fixed_per_unit`.
- `term_years`: numeric when reasonably inferable from text.
- `territory`: list of normalized geography strings.
- `evidence_text`: short supporting span, ideally one or two sentences.

## Normalization Rules

- Preserve entity meaning, but normalize spacing and punctuation.
- Do not infer missing amounts from outside the cited evidence span.
- If the filing gives a range or conditional royalty, annotate the primary disclosed rate and note ambiguity in review comments outside the gold file.
- If currency is missing, leave it blank rather than guessing.
- If term is described qualitatively, leave `term_years` blank.

## Review Workflow

1. Annotator A labels the document.
2. Annotator B reviews only positives and borderline negatives.
3. Resolve disagreements in a short adjudication note.
4. Freeze a versioned gold set snapshot before running benchmark numbers.

## Quality Checks

- No positive document with an empty `agreements` list.
- No negative document with non-empty `agreements`.
- Every positive agreement should have at least one source anchor and one evidence span.
- Sample at least 10 percent of the set for adjudication.

## How This Maps To Evaluation

The offline evaluator in `utils/evaluate_license_extraction.py` expects this shape and computes:

- document-level presence precision / recall / F1
- agreement-level precision / recall / F1
- field-level precision / recall / F1 for key structured fields

