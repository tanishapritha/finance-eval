# Finance Eval

A reproducible evaluation harness for financial agents. The project starts with ordinary finance tasks and deterministic scoring, then adds PolicyShift as a separate benchmark built on the same runner.

## Current scope

- Typed task and journal-entry schemas.
- Hand-verified synthetic finance cases.
- Deterministic ledger replay using integer minor units.
- Reference and deliberately faulty baseline agents.
- Per-case evaluation results and aggregate JSON report.
- PolicyShift is intentionally not included in this first milestone.

## Quickstart

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
python -m finance_eval run --dataset basic --agent reference
python -m finance_eval run --dataset basic --agent duplicate
python -m finance_eval report --input results/latest.jsonl
```

## Design principles

1. The agent never receives the expected answer.
2. Ledger math uses integer minor units, never floating-point currency.
3. Invalid proposed entries are reported and never posted.
4. The verifier is deterministic; LLMs are agents under evaluation, not the sole source of truth.
5. Each evaluation writes case-level JSONL so failures remain inspectable.

## Dataset

The initial dataset is synthetic and designed to test the harness, not to claim comprehensive accounting coverage. Every case includes an explicitly documented expected outcome. Expand coverage only after validating the evaluator against controlled baselines.

## Project sequence

1. Basic harness and schema.
2. Basic finance fixtures and deterministic replay.
3. Controlled-agent tests and evaluator validation.
4. Optional LLM adapter and experiment reports.
5. PolicyShift: effective-dated policy selection and downstream accounting effects.
6. Benchmark audit, reproducible experiments, and research write-up.

## Status

Early implementation. Results are engineering smoke tests, not model benchmark claims or accounting advice.
