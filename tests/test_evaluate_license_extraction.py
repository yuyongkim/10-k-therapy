import json
from pathlib import Path

from utils.evaluate_license_extraction import evaluate_paths


def test_evaluate_paths_reports_document_and_field_metrics(tmp_path: Path):
    gold_path = tmp_path / "gold.jsonl"
    gold_records = [
        {
            "document_id": "DOC_1",
            "source_system": "SEC",
            "agreement_present": True,
            "agreements": [
                {
                    "source_note_number": "12",
                    "licensor_name": "Company A",
                    "licensee_name": "Company B",
                    "technology_category": "patent_license",
                    "upfront_amount": 1000000,
                    "currency": "USD",
                }
            ],
        },
        {
            "document_id": "DOC_2",
            "source_system": "DART",
            "agreement_present": True,
            "agreements": [
                {
                    "source_section_id": "major_contracts",
                    "licensor_name": "Company C",
                    "licensee_name": "Company D",
                    "technology_category": "software_license",
                    "currency": "KRW",
                }
            ],
        },
    ]
    gold_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in gold_records),
        encoding="utf-8",
    )

    prediction_dir = tmp_path / "predictions"
    prediction_dir.mkdir()

    doc_1_prediction = {
        "document_id": "DOC_1",
        "source_info": {"system": "SEC"},
        "agreements": [
            {
                "source_note_number": "12",
                "parties": {
                    "licensor": {"name": "Company A"},
                    "licensee": {"name": "Company B"},
                },
                "technology": {"category": "patent_license"},
                "financial_terms": {
                    "upfront_payment": {"amount": 1000000, "currency": "USD"}
                },
            }
        ],
    }
    (prediction_dir / "doc1.json").write_text(
        json.dumps(doc_1_prediction, ensure_ascii=False),
        encoding="utf-8",
    )

    doc_3_prediction = {
        "document_id": "DOC_3",
        "source_info": {"system": "SEC"},
        "agreements": [
            {
                "source_note_number": "9",
                "parties": {
                    "licensor": {"name": "Extra Licensor"},
                    "licensee": {"name": "Extra Licensee"},
                },
                "technology": {"category": "trademark_license"},
                "financial_terms": {
                    "upfront_payment": {"amount": 50000, "currency": "USD"}
                },
            }
        ],
    }
    (prediction_dir / "doc3.json").write_text(
        json.dumps(doc_3_prediction, ensure_ascii=False),
        encoding="utf-8",
    )

    result = evaluate_paths(gold_path, prediction_dir)

    assert result["summary"]["gold_documents"] == 2
    assert result["summary"]["prediction_documents"] == 2

    assert result["document_presence"]["tp"] == 1
    assert result["document_presence"]["fp"] == 1
    assert result["document_presence"]["fn"] == 1

    assert result["agreement_extraction"]["tp"] == 1
    assert result["agreement_extraction"]["fp"] == 1
    assert result["agreement_extraction"]["fn"] == 1

    licensor_metrics = result["field_metrics"]["licensor_name"]
    assert licensor_metrics["exact_matches"] == 1
    assert licensor_metrics["gold_present"] == 2
    assert licensor_metrics["pred_present"] == 2
    assert licensor_metrics["precision"] == 0.5
    assert licensor_metrics["recall"] == 0.5


def test_evaluate_paths_merges_duplicate_documents_and_json_array_predictions(tmp_path: Path):
    gold_path = tmp_path / "gold.jsonl"
    gold_records = [
        {
            "document_id": "DOC_DUP",
            "source_system": "SEC",
            "agreement_present": True,
            "agreements": [
                {
                    "agreement_id": "A1",
                    "licensor_name": "Company A",
                    "licensee_name": "Company B",
                }
            ],
        },
        {
            "document_id": "DOC_DUP",
            "source_system": "SEC",
            "agreement_present": True,
            "agreements": [
                {
                    "agreement_id": "A2",
                    "licensor_name": "Company C",
                    "licensee_name": "Company D",
                }
            ],
        },
    ]
    gold_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in gold_records),
        encoding="utf-8",
    )

    prediction_dir = tmp_path / "predictions"
    prediction_dir.mkdir()
    (prediction_dir / "batch.json").write_text(
        json.dumps(
            [
                {
                    "document_id": "DOC_DUP",
                    "source_info": {"system": "SEC"},
                    "agreements": [
                        {"agreement_id": "A1", "licensor_name": "Company A", "licensee_name": "Company B"}
                    ],
                },
                {
                    "document_id": "DOC_DUP",
                    "source_info": {"system": "SEC"},
                    "agreements": [
                        {"agreement_id": "A2", "licensor_name": "Company C", "licensee_name": "Company D"}
                    ],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = evaluate_paths(gold_path, prediction_dir)

    assert result["summary"]["gold_documents"] == 1
    assert result["summary"]["prediction_documents"] == 1
    assert result["agreement_extraction"]["tp"] == 2
    assert result["agreement_extraction"]["fp"] == 0
    assert result["agreement_extraction"]["fn"] == 0


def test_evaluate_paths_skips_invalid_jsonl_rows(tmp_path: Path):
    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "document_id": "DOC_1",
                        "agreement_present": True,
                        "agreements": [{"licensor_name": "Company A"}],
                    },
                    ensure_ascii=False,
                ),
                "{not valid json}",
            ]
        ),
        encoding="utf-8",
    )

    prediction_path = tmp_path / "predictions.jsonl"
    prediction_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "document_id": "DOC_1",
                        "source_info": {"system": "SEC"},
                        "agreements": [{"licensor_name": "Company A"}],
                    },
                    ensure_ascii=False,
                ),
                "[]",
            ]
        ),
        encoding="utf-8",
    )

    result = evaluate_paths(gold_path, prediction_path)

    assert result["summary"]["gold_documents"] == 1
    assert result["summary"]["prediction_documents"] == 1
    assert result["document_presence"]["tp"] == 1
