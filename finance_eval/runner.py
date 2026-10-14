"""Experiment runner that keeps agent inputs separate from gold answers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from finance_eval.agents import FinanceAgent
from finance_eval.evaluator import evaluate
from finance_eval.schemas import EvaluationResult, FinanceTask


def run_cases(
    tasks: Iterable[FinanceTask],
    agent: FinanceAgent,
    output_path: str | Path | None = None,
) -> list[EvaluationResult]:
    results: list[EvaluationResult] = []
    for task in tasks:
        # Deliberately pass only the agent-visible view, not the FinanceTask object.
        try:
            proposal = agent.run(task.agent_view())
            result = evaluate(task, agent.name, proposal)
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            # Isolate expected agent/schema failures so the rest of a run remains inspectable.
            result = EvaluationResult(
                case_id=task.case_id,
                agent_name=agent.name,
                passed=False,
                score=0.0,
                action_exact=False,
                ledger_exact=False,
                proposed_entry_count=0,
                accepted_entry_count=0,
                errors=(f"agent execution failed: {type(exc).__name__}: {exc}",),
                closing_balances_minor=dict(task.opening_balances_minor),
                monetary_error_minor=0,
            )
        results.append(result)

    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as file:
            for result in results:
                file.write(json.dumps(result.to_dict(), sort_keys=True) + "\n")
    return results
