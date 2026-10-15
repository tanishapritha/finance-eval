# Finance Eval

A deterministic evaluation harness for financial agents. It separates **agent proposals** from **ledger verification** so a model can be evaluated on accounting decisions without relying on the model to grade its own work.

> **Status:** early research/engineering prototype. The included dataset is synthetic and small. Results are harness-validation signals, not evidence of production accounting competence, a comprehensive accounting benchmark, or accounting advice.

## What it evaluates

The first benchmark slice focuses on month-end adjustment decisions:

- Accrue services received before period-end when the invoice has not arrived.
- Do not accrue services that have not yet been received.
- Avoid duplicating expenses already posted.
- Accrue unpaid utilities consumed during the reporting period.

Each case defines agent-visible facts, a chart of accounts, opening balances, expected journal effects, and expected closing balances. Gold annotations stay separate from the task view provided to normal agents.

## Design

```text
JSONL cases
    |
    v
Dataset loader ---- schema validation
    |
    v
Agent-visible task view ---> Finance agent ---> AgentProposal
                                                  |
                                                  v
Gold labels -------------------------------> Deterministic evaluator
                                                  |
                                  +---------------+----------------+
                                  v                                v
                           Ledger replay                    Action comparison
                                  +---------------+----------------+
                                                  v
                                      Per-case JSONL results
                                                  |
                                                  v
                                       Aggregate JSON report
```

### Evaluation contract

- **Integer minor units:** monetary amounts are integers (for example, USD cents); ledger arithmetic does not use binary floating point.
- **Deterministic verification:** the ledger checks account membership, duplicate entry IDs, and debit/credit equality before posting an entry.
- **Rejected entries do not post:** a rejected entry contributes an error but does not mutate balances.
- **Two independent checks:** the evaluator compares proposed accounting effects with expected action effects and compares replayed closing balances with the expected balances.
- **Inspectability:** each case produces a JSONL result with pass/fail, action and ledger exactness, accepted/proposed entry counts, errors, balances, and monetary error.
- **No self-grading:** an agent returns a proposal; the deterministic evaluator computes the score.

### Score semantics

The current score is deliberately strict and binary:

- `1.0` only when the proposed accounting effects match the expected effects **and** replay produces the expected closing balances without ledger errors.
- `0.0` otherwise.

`monetary_error_minor` is the sum of absolute per-account differences between replayed and expected closing balances. It is a diagnostic, not a normalized metric and not directly comparable across cases with different scales. Equivalent journal entries can have different IDs or line order if their net account effects match.

## Quickstart

Requires Python 3.11 or later.

### Install from a clone

```bash
git clone https://github.com/tanishapritha/finance-eval.git
cd finance-eval

python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

python -m pip install -e ".[dev]"
```

### Run the test suite and smoke tests

```bash
ruff check .
pytest
python -m finance_eval run --dataset basic --agent reference --output results/reference.jsonl
python -m finance_eval report --input results/reference.jsonl
```

The reference agent is an **oracle-backed test fixture**, not a valid benchmark agent. It receives the private reference action only so the harness can verify that gold cases, replay, and scoring agree. Do not use its score as a model result.

### Evaluate a faulty baseline

```bash
python -m finance_eval run --dataset basic --agent duplicate --output results/duplicate.jsonl
python -m finance_eval report --input results/duplicate.jsonl --output results/duplicate-report.json
```

The command exits with status `0` when every case passes and `1` if any case fails. This makes it suitable for CI and scripted experiments. The duplicate baseline intentionally over-posts an accrual based on public task facts; it does not receive private gold labels.

Available fixture agents: `reference`, `duplicate`, `no-action`, and `always-accrue`.

### Use a custom dataset

```bash
python -m finance_eval run \
  --dataset-path path/to/cases.jsonl \
  --agent your-agent-name \
  --output results/custom-run.jsonl
```

The CLI currently resolves named dataset `basic` or an explicit JSONL path. Agent adapters are currently registered in `finance_eval/agents.py`; a stable third-party adapter API is not yet promised.

## Dataset format

The bundled dataset is at `finance_eval/data/basic.jsonl` and is included in built distributions. Each non-empty line is a JSON object representing one case. Monetary fields use integer minor units.

A simplified example:

```json
{
  "case_id": "accrual-required-001",
  "title": "Record an earned but unbilled service",
  "task_type": "accrual",
  "as_of_date": "2026-03-31",
  "currency": "USD",
  "accounts": ["Expense", "Accrued liabilities", "Cash"],
  "opening_balances_minor": {"Expense": 0, "Accrued liabilities": 0, "Cash": 100000},
  "agent_instructions": "Propose only justified adjusting entries.",
  "facts": {
    "service_received": true,
    "invoice_received": false,
    "unbilled_amount_minor": 12500
  },
  "expected_entries": [
    {
      "entry_id": "gold-accrual-required-001",
      "description": "Accrue service received before period end",
      "lines": [
        {"account": "Expense", "debit_minor": 12500},
        {"account": "Accrued liabilities", "credit_minor": 12500}
      ]
    }
  ],
  "expected_closing_balances_minor": {
    "Expense": 12500,
    "Accrued liabilities": -12500,
    "Cash": 100000
  }
}
```

The actual fixture also contains a private `reference_action` annotation nested in `facts`. The loader removes that annotation from the public `facts` before constructing the agent view. Expected entries and expected closing balances are stored separately on the task object and are not returned by `FinanceTask.agent_view()`.

Dataset validation currently checks malformed JSON/required fields, duplicate case IDs, empty datasets, non-empty account lists, and opening/expected balance account membership. The schema is still evolving; contributions should add explicit validation and tests when extending it.

## Python API

The core path is usable without an LLM provider or network access:

```python
from finance_eval.dataset import default_dataset_path, load_dataset
from finance_eval.evaluator import evaluate
from finance_eval.runner import run_cases
from finance_eval.agents import get_agent

cases = load_dataset(default_dataset_path("basic"))
results = run_cases(cases, get_agent("reference"), output_path="results/reference.jsonl")

for result in results:
    print(result.case_id, result.passed, result.monetary_error_minor)
```

For a custom agent, implement the small structural contract:

```python
class MyFinanceAgent:
    name = "my-agent"

    def run(self, task_input: dict):
        # Return finance_eval.schemas.AgentProposal.
        # task_input is the agent-visible view; it excludes gold labels.
        ...
```

The current runner uses the agent's `name` to identify fixture behavior and is intended for a single-process local experiment. A stable plugin system, parallel execution, provider-specific adapters, and a versioned external API are future work.

## Repository map

| Path | Responsibility |
| --- | --- |
| `finance_eval/schemas.py` | Typed task, proposal, journal, and result contracts |
| `finance_eval/dataset.py` | JSONL loading and case validation |
| `finance_eval/ledger.py` | Deterministic ledger replay and entry validation |
| `finance_eval/evaluator.py` | Action-effect comparison, balance comparison, scoring |
| `finance_eval/runner.py` | Agent invocation, exception isolation, JSONL output |
| `finance_eval/agents.py` | Oracle fixture and deliberately faulty baselines |
| `finance_eval/cli.py` | Run and report commands |
| `finance_eval/data/basic.jsonl` | Packaged synthetic baseline cases |
| `tests/` | Ledger, dataset, evaluator, and CLI tests |

## Reproducibility and CI

GitHub Actions runs linting, unit tests, a reference-agent smoke test, builds source/wheel distributions, and smoke-tests the installed wheel from outside the repository checkout. The out-of-checkout test is important: it catches missing package data and accidental imports from the working tree.

To reproduce the checks locally:

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
python -m build
```

## Known limitations

This project is intentionally not yet a broad finance benchmark:

- The bundled dataset contains only a handful of synthetic cases.
- It does not cover the full range of GAAP/IFRS interpretation, tax, consolidation, multi-currency accounting, reversals, materiality, or complex period cut-offs.
- The current score is binary; there are no calibrated partial-credit or severity-weighted metrics.
- The verifier checks expected accounting effects and closing balances, not the quality of the agent's natural-language explanation.
- No LLM provider, live data source, or external policy corpus is required or included.
- The fixtures are not independently audited accounting guidance.

The next engineering milestones should be broader hand-reviewed fixtures, stronger adversarial/property-based tests, explicit schema/versioning policy, experiment metadata, and a stable agent adapter contract. PolicyShift remains a separate future benchmark layer and must not be used as the sole validation of this core harness.

## Contributing

Contributions should include tests for changed behavior, preserve the gold/agent-input boundary, and keep evaluation deterministic. Do not add private reference labels to the agent-visible task view. Avoid reporting benchmark performance claims until the dataset, verifier, and experiment protocol have been independently reviewed.
