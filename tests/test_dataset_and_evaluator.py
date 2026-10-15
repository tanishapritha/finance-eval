import json

import pytest

from finance_eval.agents import get_agent
from finance_eval.dataset import default_dataset_path, load_dataset, task_from_dict
from finance_eval.evaluator import evaluate
from finance_eval.ledger import replay
from finance_eval.runner import run_cases
from finance_eval.schemas import AgentProposal, JournalEntry, JournalLine

DATASET = default_dataset_path("basic")


def test_dataset_loads_unique_cases():
    cases = load_dataset(DATASET)
    assert len(cases) >= 4
    assert len({case.case_id for case in cases}) == len(cases)


def test_gold_entries_replay_to_gold_balances():
    for case in load_dataset(DATASET):
        result = replay(case.accounts, case.opening_balances_minor, case.expected_entries)
        assert not result.errors, case.case_id
        assert result.balances_minor == {
            account: case.expected_closing_balances_minor.get(account, 0)
            for account in case.accounts
        }, case.case_id


def test_reference_agent_passes_all_cases():
    results = run_cases(load_dataset(DATASET), get_agent("reference"))
    assert all(result.passed for result in results), results


def test_no_action_agent_fails_cases_that_need_actions():
    cases = load_dataset(DATASET)
    result_by_case = {r.case_id: r for r in run_cases(cases, get_agent("no-action"))}
    assert result_by_case["accrual-required-001"].passed is False
    assert result_by_case["required-adjustment-002"].passed is False
    assert result_by_case["no-accrual-not-received-001"].passed is True


def test_duplicate_agent_posts_a_real_duplicate():
    cases = load_dataset(DATASET)
    results = run_cases(cases, get_agent("duplicate"))
    target = next(result for result in results if result.case_id == "accrual-required-001")
    assert not target.passed
    assert target.proposed_entry_count == 2
    assert target.accepted_entry_count == 2
    assert target.monetary_error_minor == 2 * 12500


def test_evaluator_uses_net_account_effect_for_entry_equivalence():
    case = load_dataset(DATASET)[0]
    gold = case.expected_entries[0]
    reordered = JournalEntry(
        "different-id",
        "equivalent entry",
        (
            JournalLine(gold.lines[1].account, credit_minor=gold.lines[1].credit_minor),
            JournalLine(gold.lines[0].account, debit_minor=gold.lines[0].debit_minor),
        ),
    )
    result = evaluate(case, "equivalent", AgentProposal((reordered,)))
    assert result.action_exact
    assert result.ledger_exact
    assert result.passed


def test_agent_view_excludes_gold_labels():
    case = load_dataset(DATASET)[0]
    view = case.agent_view()
    assert "expected_entries" not in view
    assert "expected_closing_balances_minor" not in view
    assert "reference_action" not in view["facts"]


def test_dataset_rejects_fractional_minor_units():
    raw = json.loads(DATASET.read_text(encoding="utf-8").splitlines()[0])
    raw["expected_entries"][0]["lines"][0]["debit_minor"] = 12500.5
    try:
        task_from_dict(raw)
    except ValueError as exc:
        assert "integer minor-unit" in str(exc)
    else:
        raise AssertionError("fractional minor units must be rejected")


def test_journal_line_rejects_float_amounts():
    with pytest.raises(ValueError, match="integer minor units"):
        JournalLine("Expense", debit_minor=1.5)


def test_dataset_rejects_gold_balances_that_do_not_match_entries():
    raw = json.loads(DATASET.read_text(encoding="utf-8").splitlines()[0])
    raw["expected_closing_balances_minor"]["Expense"] += 1
    with pytest.raises(ValueError, match="do not produce expected_closing_balances_minor"):
        task_from_dict(raw)


def test_evaluator_rejects_unbalanced_proposal_without_posting():
    case = load_dataset(DATASET)[0]
    invalid = JournalEntry(
        "invalid",
        "Unbalanced entry",
        (
            JournalLine("Expense", debit_minor=100),
            JournalLine("Accrued liabilities", credit_minor=90),
        ),
    )
    result = evaluate(case, "invalid-agent", AgentProposal((invalid,)))
    assert not result.passed
    assert not result.ledger_exact
    assert result.accepted_entry_count == 0
    assert any("unbalanced entry" in error for error in result.errors)


def test_agent_view_facts_are_isolated_from_mutation():
    case = load_dataset(DATASET)[0]
    view = case.agent_view()
    view["facts"]["service_received"] = False
    assert case.facts["service_received"] is True


def test_runner_records_unexpected_agent_exceptions_per_case():
    class BrokenAgent:
        name = "broken"

        def run(self, task_input):
            raise ZeroDivisionError("simulated agent failure")

    results = run_cases(load_dataset(DATASET), BrokenAgent())
    assert len(results) == len(load_dataset(DATASET))
    assert all(not result.passed for result in results)
    assert all(
        any("ZeroDivisionError" in error for error in result.errors)
        for result in results
    )


def test_runner_rejects_wrong_agent_return_type():
    class InvalidAgent:
        name = "invalid-return"

        def run(self, task_input):
            return {"entries": []}

    results = run_cases(load_dataset(DATASET), InvalidAgent())
    assert len(results) == len(load_dataset(DATASET))
    assert all(not result.passed for result in results)
    assert all(
        any("must return AgentProposal" in error for error in result.errors)
        for result in results
    )


def test_agent_name_cannot_unlock_reference_annotations():
    seen_inputs = []

    class SpoofedReferenceAgent:
        name = "reference"

        def run(self, task_input):
            seen_inputs.append(task_input)
            return AgentProposal(())

    run_cases([load_dataset(DATASET)[0]], SpoofedReferenceAgent())
    assert "_reference_action" not in seen_inputs[0]


def test_always_accrue_baseline_is_caught_on_inapplicable_case():
    results = run_cases(load_dataset(DATASET), get_agent("always-accrue"))
    target = next(
        result for result in results if result.case_id == "no-accrual-not-received-001"
    )
    assert not target.passed
    assert target.proposed_entry_count == 1
    assert target.monetary_error_minor == 2 * 12500


def test_dataset_rejects_duplicate_case_ids(tmp_path):
    first_case = DATASET.read_text(encoding="utf-8").splitlines()[0]
    dataset_path = tmp_path / "duplicate.jsonl"
    dataset_path.write_text(f"{first_case}\n{first_case}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case_id"):
        load_dataset(dataset_path)


def test_dataset_rejects_reference_annotation_mismatch():
    raw = json.loads(DATASET.read_text(encoding="utf-8").splitlines()[0])
    raw["facts"]["reference_action"]["lines"][0]["debit_minor"] += 1
    with pytest.raises(ValueError, match="reference_action does not match expected_entries"):
        task_from_dict(raw)
