import json
from pathlib import Path

from scripts.auto_validate import _extract_judge_verdict, _find_cik_directory


def test_extract_judge_verdict_handles_wrapped_json():
    raw_response = """
    Analysis complete.
    ```json
    {"licensor_correct": true, "licensee_correct": false, "is_real_license": true}
    ```
    """

    verdict = _extract_judge_verdict(raw_response)

    assert verdict == {
        "licensor_correct": True,
        "licensee_correct": False,
        "is_real_license": True,
    }


def test_extract_judge_verdict_returns_none_for_invalid_payload():
    assert _extract_judge_verdict("no json here") is None


def test_find_cik_directory_tolerates_zero_padding(tmp_path: Path):
    raw_dir = tmp_path / "raw_filings"
    raw_dir.mkdir()
    matched_dir = raw_dir / "1234"
    matched_dir.mkdir()

    found = _find_cik_directory(raw_dir, "0000001234")

    assert found == matched_dir


def test_find_cik_directory_returns_none_for_missing_root(tmp_path: Path):
    missing_root = tmp_path / "does-not-exist"

    assert _find_cik_directory(missing_root, "0000001234") is None
