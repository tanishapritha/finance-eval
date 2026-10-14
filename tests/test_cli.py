import json
from pathlib import Path

from finance_eval.cli import main


def test_cli_run_and_report(tmp_path: Path, monkeypatch):
    result_file = tmp_path / "results.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        ["finance-eval", "run", "--dataset", "basic", "--agent", "reference", "--output", str(result_file)],
    )
    assert main() == 0
    assert len(result_file.read_text(encoding="utf-8").splitlines()) == 4

    report_file = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        ["finance-eval", "report", "--input", str(result_file), "--output", str(report_file)],
    )
    assert main() == 0
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["cases"] == 4
    assert report["pass_rate"] == 1.0
