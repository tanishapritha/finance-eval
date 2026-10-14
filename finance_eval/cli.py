"""Command-line entry point for the finance evaluation harness."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from finance_eval.agents import get_agent
from finance_eval.dataset import default_dataset_path, load_dataset
from finance_eval.runner import run_cases


def _run(args: argparse.Namespace) -> int:
    dataset_path = Path(args.dataset_path) if args.dataset_path else default_dataset_path(args.dataset)
    tasks = load_dataset(dataset_path)
    agent = get_agent(args.agent)
    output = Path(args.output)
    results = run_cases(tasks, agent, output)
    passed = sum(result.passed for result in results)
    print(f"agent={agent.name} cases={len(results)} passed={passed} failed={len(results) - passed}")
    print(f"results={output}")
    return 0 if passed == len(results) else 1


def _report(args: argparse.Namespace) -> int:
    path = Path(args.input)
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    if not records:
        raise SystemExit(f"no results found in {path}")
    passed = sum(bool(record.get("passed")) for record in records)
    errors = Counter(
        error
        for record in records
        for error in record.get("errors", [])
    )
    report = {
        "input": str(path),
        "cases": len(records),
        "passed": passed,
        "failed": len(records) - passed,
        "pass_rate": passed / len(records),
        "mean_score": sum(float(record.get("score", 0.0)) for record in records) / len(records),
        "total_monetary_error_minor": sum(int(r.get("monetary_error_minor", 0)) for r in records),
        "failure_messages": dict(errors.most_common()),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finance-eval", description="Evaluate financial-agent decisions.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="evaluate an agent on a dataset")
    run.add_argument("--dataset", default="basic", help="dataset name (default: basic)")
    run.add_argument("--dataset-path", help="optional explicit JSONL dataset path")
    run.add_argument("--agent", default="reference", help="reference, duplicate, no-action, always-accrue")
    run.add_argument("--output", default="results/latest.jsonl", help="case-level JSONL output path")
    run.set_defaults(func=_run)

    report = subparsers.add_parser("report", help="aggregate a case-level JSONL result file")
    report.add_argument("--input", required=True, help="input JSONL path")
    report.add_argument("--output", help="optional aggregate JSON output path")
    report.set_defaults(func=_report)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
