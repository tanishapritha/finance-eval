from finance_eval.ledger import replay
from finance_eval.schemas import JournalEntry, JournalLine


def entry(entry_id="e1", debit_account="Expense", credit_account="Liability", amount=100):
    return JournalEntry(
        entry_id=entry_id,
        description="test",
        lines=(
            JournalLine(debit_account, debit_minor=amount),
            JournalLine(credit_account, credit_minor=amount),
        ),
    )


def test_balanced_entry_updates_balances():
    result = replay(("Expense", "Liability"), {}, (entry(),))
    assert not result.errors
    assert result.balances_minor == {"Expense": 100, "Liability": -100}


def test_unknown_account_does_not_change_ledger():
    result = replay(("Expense", "Liability"), {}, (entry(credit_account="Unknown"),))
    assert result.errors
    assert result.balances_minor == {"Expense": 0, "Liability": 0}
    assert not result.accepted_entry_ids


def test_duplicate_entry_id_is_rejected():
    first = entry()
    second = entry()
    result = replay(("Expense", "Liability"), {}, (first, second))
    assert len(result.accepted_entry_ids) == 1
    assert any("duplicate entry_id" in error for error in result.errors)
    assert result.balances_minor == {"Expense": 100, "Liability": -100}


def test_unbalanced_entry_is_rejected():
    unbalanced = JournalEntry(
        "bad", "bad", (JournalLine("Expense", debit_minor=100), JournalLine("Liability", credit_minor=90))
    )
    result = replay(("Expense", "Liability"), {}, (unbalanced,))
    assert result.errors
    assert result.balances_minor == {"Expense": 0, "Liability": 0}
