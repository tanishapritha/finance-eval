# Contributing

Thanks for helping improve Finance Eval. The project prioritizes deterministic verification, inspectable failures, and a clear boundary between agent inputs and gold annotations.

## Development setup

Use Python 3.11 or later.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check .
pytest
```

Before opening a pull request, also run the reference baseline and build the distributions:

```bash
python -m finance_eval run --dataset basic --agent reference --output /tmp/reference.jsonl
python -m finance_eval report --input /tmp/reference.jsonl
python -m build
```

## Adding a finance case

Add one JSON object per line to `finance_eval/data/basic.jsonl`. Keep cases small enough that their expected accounting treatment can be independently reviewed.

Checklist:

1. Give the case a stable, unique `case_id`; result files and regression tests use it.
2. State the reporting date, currency, task instructions, chart of accounts, opening balances, and relevant facts.
3. Represent every monetary value in integer minor units. Do not put decimal currency values in the dataset.
4. Include expected journal entries and expected closing balances for every account affected by the case.
5. If the fixture uses the oracle reference agent, include a `facts.reference_action` annotation that matches the expected entry effects. The loader validates this annotation and removes it from public facts.
6. Include both positive and negative cases where possible: the correct action, a no-action counterfactual, and duplicate/invalid proposals.
7. Run the full test suite. The loader rejects malformed cases, duplicate IDs, invalid gold entries, inconsistent closing balances, and mismatched reference annotations.

Do not add expected answers to the agent-visible facts. The private reference annotation exists only to exercise the harness; it is not an acceptable input to a real agent.

## Changing evaluation semantics

Changes to ledger replay, action equivalence, or scoring can change benchmark outcomes. For such changes:

- Add a focused regression test that fails before the change.
- Cover both valid and invalid proposals.
- Keep money arithmetic deterministic and integer-based.
- Explain the semantic change in the pull request.
- Do not compare scores across versions without recording the harness and dataset revision.

The current score is binary and the dataset is small and synthetic. Do not present it as a validated accounting benchmark or claim production accounting competence from these fixtures.

## Pull requests

Keep changes focused, document externally visible behavior, and include tests. Avoid adding provider-specific dependencies to the deterministic core unless they are needed by the core contract. PolicyShift remains a separate benchmark layer and must not be the only validation of the core harness.
