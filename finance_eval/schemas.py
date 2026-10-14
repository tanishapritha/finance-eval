"""Typed contracts shared by datasets, agents, ledger replay, and scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class JournalLine:
    account: str
    debit_minor: int = 0
    credit_minor: int = 0

    def __post_init__(self) -> None:
        if not self.account.strip():
            raise ValueError("account must not be empty")
        if self.debit_minor < 0 or self.credit_minor < 0:
            raise ValueError("debit and credit amounts must be non-negative")
        if self.debit_minor and self.credit_minor:
            raise ValueError("a journal line cannot have both debit and credit amounts")
        if not self.debit_minor and not self.credit_minor:
            raise ValueError("a journal line must have a debit or credit amount")


@dataclass(frozen=True)
class JournalEntry:
    entry_id: str
    description: str
    lines: tuple[JournalLine, ...]

    def __post_init__(self) -> None:
        if not self.entry_id.strip():
            raise ValueError("entry_id must not be empty")
        if len(self.lines) < 2:
            raise ValueError("journal entry must contain at least two lines")


@dataclass(frozen=True)
class FinanceTask:
    case_id: str
    title: str
    task_type: str
    as_of_date: str
    currency: str
    accounts: tuple[str, ...]
    opening_balances_minor: dict[str, int]
    agent_instructions: str
    facts: dict[str, Any]
    expected_entries: tuple[JournalEntry, ...] = field(repr=False)
    expected_closing_balances_minor: dict[str, int] = field(repr=False)

    def agent_view(self) -> dict[str, Any]:
        """Return only task inputs. Gold data must never be exposed to agents."""
        return {
            "case_id": self.case_id,
            "title": self.title,
            "task_type": self.task_type,
            "as_of_date": self.as_of_date,
            "currency": self.currency,
            "accounts": list(self.accounts),
            "opening_balances_minor": dict(self.opening_balances_minor),
            "agent_instructions": self.agent_instructions,
            "facts": self.facts,
        }


@dataclass(frozen=True)
class AgentProposal:
    entries: tuple[JournalEntry, ...]
    rationale: str = ""


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    agent_name: str
    passed: bool
    score: float
    action_exact: bool
    ledger_exact: bool
    proposed_entry_count: int
    accepted_entry_count: int
    errors: tuple[str, ...]
    closing_balances_minor: dict[str, int]
    monetary_error_minor: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "agent_name": self.agent_name,
            "passed": self.passed,
            "score": self.score,
            "action_exact": self.action_exact,
            "ledger_exact": self.ledger_exact,
            "proposed_entry_count": self.proposed_entry_count,
            "accepted_entry_count": self.accepted_entry_count,
            "errors": list(self.errors),
            "closing_balances_minor": self.closing_balances_minor,
            "monetary_error_minor": self.monetary_error_minor,
            "metadata": self.metadata,
        }
