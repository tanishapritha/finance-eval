"""Deterministic agents used to validate that the evaluator catches known failures."""

from __future__ import annotations

from typing import Protocol

from finance_eval.schemas import AgentProposal, JournalEntry, JournalLine


class FinanceAgent(Protocol):
    name: str

    def run(self, task_input: dict) -> AgentProposal:
        """Produce proposed entries from agent-visible task input only."""


class ReferenceAgent:
    """Fixture-only oracle baseline; never pass private gold annotations to real agents."""

    name = "reference"

    def run(self, task_input: dict) -> AgentProposal:
        # This agent is only for harness smoke tests and receives the parsed task object separately.
        action = task_input.get("_reference_action")
        if not action:
            return AgentProposal(entries=(), rationale="No fixture reference action.")
        entry = JournalEntry(
            entry_id=f"ref-{task_input['case_id']}",
            description=str(action["description"]),
            lines=tuple(
                JournalLine(
                    account=str(line["account"]),
                    debit_minor=int(line.get("debit_minor", 0)),
                    credit_minor=int(line.get("credit_minor", 0)),
                )
                for line in action["lines"]
            ),
        )
        return AgentProposal((entry,), rationale="Fixture-driven reference agent for harness validation.")


class DuplicateEntryAgent:
    """Faulty baseline that duplicates an accrual inferred from public task facts.

    Unlike the reference baseline, this agent does not receive the private reference action.
    It is intentionally narrow and exists to test whether the evaluator catches over-posting.
    """

    name = "duplicate"

    def run(self, task_input: dict) -> AgentProposal:
        facts = task_input["facts"]
        amount = facts.get("unbilled_amount_minor")
        accounts = task_input["accounts"]
        expense_account = next(
            (account for account in accounts if "expense" in account.casefold()),
            None,
        )
        liability_account = next(
            (account for account in accounts if account.casefold() == "accrued liabilities"),
            None,
        )
        if (
            not facts.get("service_received")
            or facts.get("invoice_received")
            or not isinstance(amount, int)
            or amount <= 0
            or expense_account is None
            or liability_account is None
        ):
            return AgentProposal((), rationale="Fault injection not applicable to this task.")
        lines = (
            JournalLine(expense_account, debit_minor=amount),
            JournalLine(liability_account, credit_minor=amount),
        )
        entries = (
            JournalEntry(f"duplicate-{task_input['case_id']}-1", "First accrual", lines),
            JournalEntry(f"duplicate-{task_input['case_id']}-2", "Duplicate accrual", lines),
        )
        return AgentProposal(entries, rationale="Fault injection: posts the same accrual twice.")


class NoActionAgent:
    name = "no-action"

    def run(self, task_input: dict) -> AgentProposal:
        return AgentProposal((), rationale="Fault injection: ignores all required actions.")


class AlwaysAccrueAgent:
    name = "always-accrue"

    def run(self, task_input: dict) -> AgentProposal:
        facts = task_input["facts"]
        amount = facts.get("unbilled_amount_minor")
        if amount is None or amount <= 0:
            return AgentProposal(())
        # This baseline is intended for these fixtures' chart of accounts.
        if "Expense" not in task_input["accounts"] or "Accrued liabilities" not in task_input["accounts"]:
            return AgentProposal((), rationale="Fault injection not applicable to this chart of accounts.")
        entry = JournalEntry(
            entry_id=f"accrue-{task_input['case_id']}",
            description="Accrue every unbilled amount regardless of the task requirement.",
            lines=(
                JournalLine("Expense", debit_minor=int(amount)),
                JournalLine("Accrued liabilities", credit_minor=int(amount)),
            ),
        )
        return AgentProposal((entry,), rationale="Fault injection: accrues without checking applicability.")


def get_agent(name: str) -> FinanceAgent:
    agents: dict[str, FinanceAgent] = {
        "reference": ReferenceAgent(),
        "duplicate": DuplicateEntryAgent(),
        "no-action": NoActionAgent(),
        "always-accrue": AlwaysAccrueAgent(),
    }
    try:
        return agents[name]
    except KeyError as exc:
        raise ValueError(f"unknown agent {name!r}; choose one of {', '.join(agents)}") from exc
