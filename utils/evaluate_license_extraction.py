import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


MATCH_THRESHOLD = 2.0
STRING_FIELDS = [
    "agreement_id",
    "source_section_id",
    "source_note_number",
    "licensor_name",
    "licensee_name",
    "technology_name",
    "technology_category",
    "industry",
    "currency",
    "royalty_unit",
]
NUMERIC_FIELDS = [
    "upfront_amount",
    "royalty_rate",
    "term_years",
]
LIST_FIELDS = [
    "territory",
]
REPORT_FIELDS = [
    "licensor_name",
    "licensee_name",
    "technology_category",
    "upfront_amount",
    "currency",
    "royalty_rate",
    "royalty_unit",
    "term_years",
    "source_note_number",
    "source_section_id",
]


def _safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _normalize_text(value: Any) -> str:
    text = _safe_text(value).lower()
    cleaned = []
    for char in text:
        cleaned.append(char if char.isalnum() else " ")
    return " ".join("".join(cleaned).split())


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    normalized = [_normalize_text(item) for item in items if _normalize_text(item)]
    return sorted(set(normalized))


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _safe_text(value).replace(",", "")
    if not text:
        return None
    chars = []
    seen_digit = False
    for char in text:
        if char.isdigit() or char in ".-":
            chars.append(char)
            if char.isdigit():
                seen_digit = True
        elif seen_digit:
            break
    numeric = "".join(chars).strip()
    if not numeric or numeric in {".", "-", "-."}:
        return None
    try:
        return float(numeric)
    except ValueError:
        return None


def _nested(payload: Dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _agreement_signature(agreement: Dict[str, Any]) -> Tuple[str, ...]:
    return (
        _normalize_text(agreement.get("agreement_id")),
        _normalize_text(agreement.get("licensor_name")),
        _normalize_text(agreement.get("licensee_name")),
        _normalize_text(agreement.get("technology_name")),
        _normalize_text(agreement.get("source_note_number")),
        _normalize_text(agreement.get("source_section_id")),
    )


def _field_present(field: str, agreement: Dict[str, Any]) -> bool:
    value = agreement.get(field)
    if field in LIST_FIELDS:
        return bool(_normalize_list(value))
    if field in NUMERIC_FIELDS:
        return _parse_float(value) is not None
    return bool(_normalize_text(value))


def _values_match(field: str, gold_value: Any, pred_value: Any) -> bool:
    if field in LIST_FIELDS:
        return _normalize_list(gold_value) == _normalize_list(pred_value) and bool(_normalize_list(gold_value))
    if field in NUMERIC_FIELDS:
        gold_num = _parse_float(gold_value)
        pred_num = _parse_float(pred_value)
        if gold_num is None or pred_num is None:
            return False
        tolerance = 0.01 if field == "royalty_rate" else 1.0
        return math.isclose(gold_num, pred_num, rel_tol=1e-4, abs_tol=tolerance)
    return _normalize_text(gold_value) == _normalize_text(pred_value) and bool(_normalize_text(gold_value))


def normalize_agreement(agreement: Dict[str, Any]) -> Dict[str, Any]:
    parties = agreement.get("parties", {}) if isinstance(agreement.get("parties"), dict) else {}
    licensor = parties.get("licensor", {}) if isinstance(parties.get("licensor"), dict) else {}
    licensee = parties.get("licensee", {}) if isinstance(parties.get("licensee"), dict) else {}
    technology = agreement.get("technology", {}) if isinstance(agreement.get("technology"), dict) else {}
    financial_terms = agreement.get("financial_terms", {}) if isinstance(agreement.get("financial_terms"), dict) else {}
    upfront = financial_terms.get("upfront_payment", {}) if isinstance(financial_terms.get("upfront_payment"), dict) else {}
    royalty = financial_terms.get("royalty", {}) if isinstance(financial_terms.get("royalty"), dict) else {}
    contract_terms = agreement.get("contract_terms", {}) if isinstance(agreement.get("contract_terms"), dict) else {}
    term = contract_terms.get("term", {}) if isinstance(contract_terms.get("term"), dict) else {}
    territory = contract_terms.get("territory", {}) if isinstance(contract_terms.get("territory"), dict) else {}

    return {
        "agreement_id": _safe_text(agreement.get("agreement_id")),
        "source_section_id": _safe_text(agreement.get("source_section_id")),
        "source_note_number": _safe_text(agreement.get("source_note_number")),
        "licensor_name": _safe_text(agreement.get("licensor_name") or licensor.get("name")),
        "licensee_name": _safe_text(agreement.get("licensee_name") or licensee.get("name")),
        "technology_name": _safe_text(agreement.get("technology_name") or technology.get("name")),
        "technology_category": _safe_text(agreement.get("technology_category") or technology.get("category")),
        "industry": _safe_text(agreement.get("industry")),
        "upfront_amount": agreement.get("upfront_amount", upfront.get("amount")),
        "currency": _safe_text(agreement.get("currency") or upfront.get("currency")),
        "royalty_rate": agreement.get("royalty_rate", royalty.get("rate")),
        "royalty_unit": _safe_text(agreement.get("royalty_unit") or royalty.get("unit")),
        "term_years": agreement.get("term_years", term.get("years")),
        "territory": agreement.get("territory", territory.get("geographic")),
        "evidence_text": _safe_text(agreement.get("evidence_text")),
    }


def _iter_records_from_payload(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, dict):
        yield payload
        return
    if isinstance(payload, list):
        for record in payload:
            yield from _iter_records_from_payload(record)


def _iter_json_payloads(path: Path) -> Iterable[Dict[str, Any]]:
    if path.is_dir():
        for json_path in sorted(path.rglob("*.json")):
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
            except json.JSONDecodeError:
                continue
            yield from _iter_records_from_payload(payload)
        return

    if path.suffix.lower() == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield from _iter_records_from_payload(payload)
        return

    payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    yield from _iter_records_from_payload(payload)


def _merge_documents(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    agreements = existing.setdefault("agreements", [])
    seen = {_agreement_signature(agreement) for agreement in agreements}
    for agreement in incoming.get("agreements", []):
        signature = _agreement_signature(agreement)
        if signature in seen:
            continue
        agreements.append(agreement)
        seen.add(signature)

    existing["agreement_present"] = bool(
        existing.get("agreement_present") or incoming.get("agreement_present") or agreements
    )
    existing["source_system"] = existing.get("source_system") or incoming.get("source_system") or ""
    return existing


def load_gold_documents(path: Path) -> Dict[str, Dict[str, Any]]:
    documents: Dict[str, Dict[str, Any]] = {}
    for record in _iter_json_payloads(path):
        payload = record.get("gold") if isinstance(record.get("gold"), dict) else record
        document_id = _safe_text(payload.get("document_id"))
        if not document_id:
            continue
        agreements = payload.get("agreements", []) if isinstance(payload.get("agreements"), list) else []
        normalized = {
            "document_id": document_id,
            "source_system": _safe_text(payload.get("source_system")),
            "agreement_present": bool(payload.get("agreement_present", bool(agreements))),
            "agreements": [normalize_agreement(agreement) for agreement in agreements if isinstance(agreement, dict)],
        }
        if document_id in documents:
            documents[document_id] = _merge_documents(documents[document_id], normalized)
        else:
            documents[document_id] = normalized
    return documents


def load_prediction_documents(path: Path) -> Dict[str, Dict[str, Any]]:
    documents: Dict[str, Dict[str, Any]] = {}
    for record in _iter_json_payloads(path):
        payload = record.get("prediction") if isinstance(record.get("prediction"), dict) else record
        document_id = _safe_text(payload.get("document_id"))
        if not document_id:
            continue
        agreements = payload.get("agreements", []) if isinstance(payload.get("agreements"), list) else []
        normalized = {
            "document_id": document_id,
            "source_system": _safe_text(_nested(payload, "source_info", "system") or payload.get("source_system")),
            "agreement_present": bool(agreements),
            "agreements": [normalize_agreement(agreement) for agreement in agreements if isinstance(agreement, dict)],
        }
        if document_id in documents:
            documents[document_id] = _merge_documents(documents[document_id], normalized)
        else:
            documents[document_id] = normalized
    return documents


def _agreement_match_score(gold: Dict[str, Any], pred: Dict[str, Any]) -> float:
    gold_id = gold.get("agreement_id")
    pred_id = pred.get("agreement_id")
    if gold_id and pred_id and _values_match("agreement_id", gold_id, pred_id):
        return 100.0

    score = 0.0
    if _values_match("licensor_name", gold.get("licensor_name"), pred.get("licensor_name")):
        score += 2.0
    if _values_match("licensee_name", gold.get("licensee_name"), pred.get("licensee_name")):
        score += 2.0
    if _values_match("technology_category", gold.get("technology_category"), pred.get("technology_category")):
        score += 1.0
    if _values_match("source_note_number", gold.get("source_note_number"), pred.get("source_note_number")):
        score += 1.0
    if _values_match("source_section_id", gold.get("source_section_id"), pred.get("source_section_id")):
        score += 1.0
    if _values_match("industry", gold.get("industry"), pred.get("industry")):
        score += 0.5
    return score


def match_agreements(
    gold_agreements: List[Dict[str, Any]],
    pred_agreements: List[Dict[str, Any]],
) -> List[Tuple[int, int, float]]:
    candidates: List[Tuple[float, int, int]] = []
    for gold_index, gold in enumerate(gold_agreements):
        for pred_index, pred in enumerate(pred_agreements):
            score = _agreement_match_score(gold, pred)
            if score >= MATCH_THRESHOLD:
                candidates.append((score, gold_index, pred_index))

    matches: List[Tuple[int, int, float]] = []
    used_gold = set()
    used_pred = set()
    for score, gold_index, pred_index in sorted(candidates, key=lambda item: (-item[0], item[1], item[2])):
        if gold_index in used_gold or pred_index in used_pred:
            continue
        used_gold.add(gold_index)
        used_pred.add(pred_index)
        matches.append((gold_index, pred_index, score))
    return matches


def _prf(tp: int, fp: int, fn: int) -> Dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_documents(
    gold_documents: Dict[str, Dict[str, Any]],
    prediction_documents: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    doc_tp = doc_fp = doc_fn = 0
    agreement_tp = agreement_fp = agreement_fn = 0
    field_counts = {
        field: {
            "gold_present": 0,
            "pred_present": 0,
            "exact_matches": 0,
        }
        for field in REPORT_FIELDS
    }
    unmatched_gold_documents: List[str] = []
    extra_prediction_documents: List[str] = []
    matched_pairs_total = 0

    all_document_ids = sorted(set(gold_documents) | set(prediction_documents))
    for document_id in all_document_ids:
        gold_doc = gold_documents.get(document_id, {"agreement_present": False, "agreements": []})
        pred_doc = prediction_documents.get(document_id, {"agreements": []})

        gold_positive = bool(gold_doc.get("agreement_present") or gold_doc.get("agreements"))
        pred_positive = bool(pred_doc.get("agreements"))

        if gold_positive and pred_positive:
            doc_tp += 1
        elif pred_positive and not gold_positive:
            doc_fp += 1
            extra_prediction_documents.append(document_id)
        elif gold_positive and not pred_positive:
            doc_fn += 1
            unmatched_gold_documents.append(document_id)

        gold_agreements = gold_doc.get("agreements", [])
        pred_agreements = pred_doc.get("agreements", [])
        matches = match_agreements(gold_agreements, pred_agreements)
        matched_pairs_total += len(matches)

        agreement_tp += len(matches)
        agreement_fp += max(len(pred_agreements) - len(matches), 0)
        agreement_fn += max(len(gold_agreements) - len(matches), 0)

        for agreement in gold_agreements:
            for field in REPORT_FIELDS:
                if _field_present(field, agreement):
                    field_counts[field]["gold_present"] += 1

        for agreement in pred_agreements:
            for field in REPORT_FIELDS:
                if _field_present(field, agreement):
                    field_counts[field]["pred_present"] += 1

        for gold_index, pred_index, _ in matches:
            gold_agreement = gold_agreements[gold_index]
            pred_agreement = pred_agreements[pred_index]
            for field in REPORT_FIELDS:
                if _values_match(field, gold_agreement.get(field), pred_agreement.get(field)):
                    field_counts[field]["exact_matches"] += 1

    field_metrics = {}
    for field, counts in field_counts.items():
        metrics = _prf(
            counts["exact_matches"],
            max(counts["pred_present"] - counts["exact_matches"], 0),
            max(counts["gold_present"] - counts["exact_matches"], 0),
        )
        field_metrics[field] = {
            **counts,
            **metrics,
        }

    return {
        "summary": {
            "gold_documents": len(gold_documents),
            "prediction_documents": len(prediction_documents),
            "scored_documents": len(all_document_ids),
            "matched_agreement_pairs": matched_pairs_total,
            "match_threshold": MATCH_THRESHOLD,
        },
        "document_presence": _prf(doc_tp, doc_fp, doc_fn),
        "agreement_extraction": _prf(agreement_tp, agreement_fp, agreement_fn),
        "field_metrics": field_metrics,
        "diagnostics": {
            "documents_missing_predictions": unmatched_gold_documents[:25],
            "documents_only_in_predictions": extra_prediction_documents[:25],
        },
    }


def evaluate_paths(gold_path: Path, prediction_path: Path) -> Dict[str, Any]:
    gold_documents = load_gold_documents(gold_path)
    prediction_documents = load_prediction_documents(prediction_path)
    return evaluate_documents(gold_documents, prediction_documents)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate license extraction against a gold set")
    parser.add_argument("--gold", required=True, help="Gold annotations in JSON or JSONL")
    parser.add_argument(
        "--predictions",
        required=True,
        help="Prediction file or directory containing unified schema JSON outputs",
    )
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    result = evaluate_paths(Path(args.gold), Path(args.predictions))
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    print(serialized)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
