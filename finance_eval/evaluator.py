"""Deterministic evaluator for proposed finance actions."""

from __future__ import annotations

from collections import Counter

from finance_eval.ledger import entry_net_effect, replay
from finance_eval.schemas import AgentProposal, EvaluationResult, FinanceTask, JournalEntry


def _entry_signature(entry: JournalEntry) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(entry_net_effect(entry).items()))


def _action_counts(entries: tuple[JournalEntry, ...]) -> Counter[tuple[tuple[str, int], ...]]:
    return Counter(_entry_signature(entry) for entry in entries)


def evaluate(task: FinanceTask, agent_name: str, proposal: AgentProposal) -> EvaluationResult:
    """Score a proposal without exposing gold data to the agent."""
    replay_result = replay(task.accounts, task.opening_balances_minor, proposal.entries)
    expected = replay(task.accounts, task.opening_balances_minor, task.expected_entries)

    expected_counts = _action_counts(task.expected_entries)
    proposed_counts = _action_counts(proposal.entries)
    action_exact = expected_counts == proposed_counts

    all_accounts = set(task.accounts)
    closing_exact = all(
        replay_result.balances_minor.get(account, 0)
        == task.expected_closing_balances_minor.get(account, 0)
        for account in all_accounts
    )
    monetary_error = sum(
        abs(
            replay_result.balances_minor.get(account, 0)
            - task.expected_closing_balances_minor.get(account, 0)
        )
        for account in all_accounts
    )
    ledger_exact = closing_exact and not replay_result.errors
    passed = action_exact and ledger_exact
    score = 1.0 if passed else 0.0

    errors = list(replay_result.errors)
    if not action_exact:
        errors.append("proposed journal actions do not match the gold accounting effects")
    if not closing_exact:
        errors.append("closing balances differ from expected balances")
    if expected.errors:
        errors.append("dataset gold entries failed ledger validation: " + "; ".join(expected.errors))

    return EvaluationResult(
        case_id=task.case_id,
        agent_name=agent_name,
        passed=passed,
        score=score,
        action_exact=action_exact,
        ledger_exact=ledger_exact,
        proposed_entry_count=len(proposal.entries),
        accepted_entry_count=len(replay_result.accepted_entry_ids),
        errors=tuple(errors),
        closing_balances_minor=replay_result.balances_minor,
        monetary_error_minor=monetary_error,
    )
