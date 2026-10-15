from __future__ import annotations

import json
from pathlib import Path

import pytest

from co_extract.cli import main
from co_extract.schema import ExtractionResult
from tests.conftest import SAMPLES

CLEAN = str(SAMPLES / "co_001_clean.txt")


def test_prints_valid_json_for_one_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([CLEAN]) == 0
    result = ExtractionResult.model_validate_json(capsys.readouterr().out)
    assert result.change_order.change_order_number.value == "CO-014"


def test_out_dir_writes_one_file_per_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    flagged = str(SAMPLES / "co_005_sum_mismatch.txt")
    assert main([CLEAN, flagged, "--out-dir", str(tmp_path / "out")]) == 0
    written = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert written == ["co_001_clean.json", "co_005_sum_mismatch.json"]
    summary = capsys.readouterr().out
    assert "co_001_clean.txt: ok" in summary
    assert "co_005_sum_mismatch.txt: REVIEW" in summary
    assert json.loads((tmp_path / "out" / "co_001_clean.json").read_text())["needs_review"] is False


def test_min_confidence_flag_changes_routing(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([CLEAN, "--min-confidence", "0.99"]) == 0
    assert json.loads(capsys.readouterr().out)["needs_review"] is True


def test_bad_file_is_reported_and_other_files_still_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["missing.pdf", CLEAN]) == 1
    captured = capsys.readouterr()
    assert "missing.pdf: file not found" in captured.err
    assert json.loads(captured.out)["source"] == "co_001_clean.txt"


def test_print_schema(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--print-schema"]) == 0
    assert "ExtractionResult" in capsys.readouterr().out


def test_no_arguments_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_llm_flag_without_api_key_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main([CLEAN, "--llm"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_split_writes_one_file_per_change_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    packet = str(SAMPLES / "co_010_packet.txt")
    assert main([packet, "--split", "--out-dir", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "co_010_packet_01.json",
        "co_010_packet_02.json",
    ]
    assert capsys.readouterr().out.count("->") == 2


def test_folder_input_and_csv_summary(tmp_path: Path) -> None:
    import csv
    import shutil

    folder = tmp_path / "in"
    folder.mkdir()
    for sample in SAMPLES.glob("*.txt"):
        shutil.copy(sample, folder)
    summary = tmp_path / "summary.csv"
    args = [str(folder), "--split", "--summary", str(summary), "--out-dir", str(tmp_path / "o")]
    assert main(args) == 0
    rows = list(csv.DictReader(summary.open(encoding="utf-8")))
    by_source = {r["source"]: r for r in rows}
    assert by_source["co_001_clean.txt"]["needs_review"] == "False"
    assert by_source["co_005_sum_mismatch.txt"]["needs_review"] == "True"
    assert "contract_sum_mismatch" in by_source["co_005_sum_mismatch.txt"]["issues"]
    assert {"co_010_packet.txt#1", "co_010_packet.txt#2"} <= by_source.keys()


def test_llm_fallback_without_a_key_is_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main([CLEAN, "--llm-fallback"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
