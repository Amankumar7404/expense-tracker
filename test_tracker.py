import pytest

from tracker import (
    add_expense,
    delete_expense,
    filter_by_category,
    load_expenses,
    save_expenses,
    summarize,
)


def test_add_expense_assigns_incrementing_ids():
    expenses = []
    first = add_expense(expenses, 100, "Food", "Lunch")
    second = add_expense(expenses, 50, "travel")
    assert first["id"] == 1
    assert second["id"] == 2
    assert first["category"] == "food"  # normalized to lowercase


def test_add_expense_rejects_bad_input():
    with pytest.raises(ValueError):
        add_expense([], 0, "food")
    with pytest.raises(ValueError):
        add_expense([], -5, "food")
    with pytest.raises(ValueError):
        add_expense([], 10, "   ")


def test_delete_expense():
    expenses = []
    add_expense(expenses, 10, "food")
    assert delete_expense(expenses, 1) is True
    assert delete_expense(expenses, 1) is False
    assert expenses == []


def test_filter_by_category():
    expenses = []
    add_expense(expenses, 10, "food")
    add_expense(expenses, 20, "travel")
    add_expense(expenses, 5, "Food")
    assert len(filter_by_category(expenses, "FOOD")) == 2


def test_summarize():
    expenses = []
    add_expense(expenses, 10.5, "food")
    add_expense(expenses, 4.5, "food")
    add_expense(expenses, 20, "travel")
    total, by_category = summarize(expenses)
    assert total == 35.0
    assert by_category == {"food": 15.0, "travel": 20.0}


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "data.json"
    expenses = []
    add_expense(expenses, 99.99, "bills", "Internet")
    save_expenses(expenses, path)
    assert load_expenses(path) == expenses


def test_load_missing_file_returns_empty(tmp_path):
    assert load_expenses(tmp_path / "nope.json") == []


def test_load_corrupted_file_returns_empty(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")
    assert load_expenses(path) == []
