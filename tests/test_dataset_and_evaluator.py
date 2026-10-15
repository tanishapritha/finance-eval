from finance_eval.agents import get_agent
from finance_eval.dataset import load_dataset, default_dataset_path
from finance_eval.evaluator import evaluate
from finance_eval.runner import run_cases
from finance_eval.schemas import AgentProposal, JournalEntry, JournalLine


DATASET = default_dataset_path("basic")


def test_dataset_loads_unique_cases():
    cases = load_dataset(DATASET)
    assert len(cases) >= 4
    assert len({case.case_id for case in cases}) == len(cases)


def test_gold_entries_replay_to_gold_balances():
    from finance_eval.ledger import replay

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
