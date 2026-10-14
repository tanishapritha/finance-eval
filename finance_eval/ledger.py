"""Deterministic ledger replay with amounts represented as integer minor units."""

from __future__ import annotations

from dataclasses import dataclass

from finance_eval.schemas import JournalEntry


@dataclass(frozen=True)
class ReplayResult:
    balances_minor: dict[str, int]
    accepted_entry_ids: tuple[str, ...]
    errors: tuple[str, ...]


def entry_net_effect(entry: JournalEntry) -> dict[str, int]:
    """Return debit-positive net effects by account for equivalence comparisons."""
    effects: dict[str, int] = {}
    for line in entry.lines:
        effects[line.account] = effects.get(line.account, 0) + line.debit_minor - line.credit_minor
    return {account: amount for account, amount in effects.items() if amount != 0}


def replay(
    accounts: tuple[str, ...],
    opening_balances_minor: dict[str, int],
    entries: tuple[JournalEntry, ...],
) -> ReplayResult:
    """Validate and apply entries independently; rejected entries never affect balances."""
    allowed = set(accounts)
    balances = {account: int(opening_balances_minor.get(account, 0)) for account in accounts}
    errors: list[str] = []
    accepted: list[str] = []
    seen_ids: set[str] = set()

    for entry in entries:
        prefix = f"entry {entry.entry_id!r}"
        if entry.entry_id in seen_ids:
            errors.append(f"{prefix}: duplicate entry_id")
            continue
        seen_ids.add(entry.entry_id)

        unknown = sorted({line.account for line in entry.lines} - allowed)
        if unknown:
            errors.append(f"{prefix}: unknown account(s): {', '.join(unknown)}")
            continue

        debit = sum(line.debit_minor for line in entry.lines)
        credit = sum(line.credit_minor for line in entry.lines)
        if debit != credit:
            errors.append(f"{prefix}: unbalanced entry (debits={debit}, credits={credit})")
            continue

        for line in entry.lines:
            balances[line.account] += line.debit_minor - line.credit_minor
        accepted.append(entry.entry_id)

    return ReplayResult(balances, tuple(accepted), tuple(errors))
