"""Loading and validation for synthetic finance JSONL cases.

Gold labels are stored in the dataset but kept separate from the facts passed to agents.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from finance_eval.ledger import replay
from finance_eval.schemas import FinanceTask, JournalEntry, JournalLine


def _integer(value: Any, field: str) -> int:
    """Require a JSON integer; never silently truncate floats or coerce strings."""
    if type(value) is not int:
        raise ValueError(f"{field} must be an integer minor-unit amount")
    return value


def _entry_from_dict(raw: dict[str, Any]) -> JournalEntry:
    return JournalEntry(
        entry_id=str(raw["entry_id"]),
        description=str(raw.get("description", "")),
        lines=tuple(
            JournalLine(
                account=str(line["account"]),
                debit_minor=_integer(line.get("debit_minor", 0), "debit_minor"),
                credit_minor=_integer(line.get("credit_minor", 0), "credit_minor"),
            )
            for line in raw["lines"]
        ),
    )


def task_from_dict(raw: dict[str, Any]) -> FinanceTask:
    facts = dict(raw.get("facts", {}))
    reference_action = facts.pop("reference_action", None)
    task = FinanceTask(
        case_id=str(raw["case_id"]),
        title=str(raw["title"]),
        task_type=str(raw["task_type"]),
        as_of_date=str(raw["as_of_date"]),
        currency=str(raw.get("currency", "USD")),
        accounts=tuple(str(a) for a in raw["accounts"]),
        opening_balances_minor={str(k): _integer(v, f"opening_balances_minor[{k!r}]") for k, v in raw["opening_balances_minor"].items()},
        agent_instructions=str(raw["agent_instructions"]),
        facts=facts,
        reference_action=reference_action,
        expected_entries=tuple(_entry_from_dict(e) for e in raw["expected_entries"]),
        expected_closing_balances_minor={
            str(k): _integer(v, f"expected_closing_balances_minor[{k!r}]") for k, v in raw["expected_closing_balances_minor"].items()
        },
    )
    if not task.case_id:
        raise ValueError("case_id must not be empty")
    if not task.accounts:
        raise ValueError(f"{task.case_id}: accounts must not be empty")
    if len(set(task.accounts)) != len(task.accounts):
        raise ValueError(f"{task.case_id}: account names must be unique")
    unknown_opening = set(task.opening_balances_minor) - set(task.accounts)
    unknown_expected = set(task.expected_closing_balances_minor) - set(task.accounts)
    if unknown_opening:
        raise ValueError(f"{task.case_id}: unknown opening accounts: {sorted(unknown_opening)}")
    if unknown_expected:
        raise ValueError(f"{task.case_id}: unknown expected accounts: {sorted(unknown_expected)}")
    gold_replay = replay(task.accounts, task.opening_balances_minor, task.expected_entries)
    if gold_replay.errors:
        raise ValueError(f"{task.case_id}: invalid expected_entries")
    expected_balances = {
        account: task.expected_closing_balances_minor.get(account, 0) for account in task.accounts
    }
    if gold_replay.balances_minor != expected_balances:
        raise ValueError(
            f"{task.case_id}: expected_entries do not produce expected_closing_balances_minor"
        )
    return task


def load_dataset(path: str | Path) -> list[FinanceTask]:
    """Load JSONL cases and reject duplicate IDs or malformed rows."""
    dataset_path = Path(path)
    cases: list[FinanceTask] = []
    seen: set[str] = set()
    for line_number, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
            case = task_from_dict(raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{dataset_path}:{line_number}: {exc}") from exc
        if case.case_id in seen:
            raise ValueError(f"{dataset_path}:{line_number}: duplicate case_id {case.case_id!r}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError(f"dataset is empty: {dataset_path}")
    return cases


def default_dataset_path(name: str) -> Path:
    if name != "basic":
        raise ValueError(f"unknown dataset {name!r}; available dataset: basic")
    return Path(__file__).resolve().parent / "data" / "basic.jsonl"
