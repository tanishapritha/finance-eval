"""Deterministic agents used to validate that the evaluator catches known failures."""

from __future__ import annotations

from typing import Protocol

from finance_eval.schemas import AgentProposal, FinanceTask, JournalEntry, JournalLine


class FinanceAgent(Protocol):
    name: str

    def run(self, task_input: dict) -> AgentProposal:
        """Produce proposed entries from agent-visible task input only."""


class ReferenceAgent:
    """Fixture-only reference agent; never pass private gold annotations to real agents."""

    name = "reference"

    def run(self, task_input: dict) -> AgentProposal:
        # The runner attaches no gold labels to task_input. Its private test hook is separate.
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
    name = "duplicate"

    def run(self, task_input: dict) -> AgentProposal:
        proposal = ReferenceAgent().run(task_input)
        if not proposal.entries:
            return proposal
        original = proposal.entries[0]
        duplicate = JournalEntry(
            entry_id=original.entry_id + "-duplicate",
            description=original.description,
            lines=original.lines,
        )
        return AgentProposal(
            entries=proposal.entries + (duplicate,),
            rationale="Fault injection: posts the same action twice.",
        )


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
