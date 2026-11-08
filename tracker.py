"""Expense Tracker - a simple command-line app to record and review spending.

Usage examples:
    python tracker.py add 250 food "Lunch with friends"
    python tracker.py list
    python tracker.py list --category food
    python tracker.py summary
    python tracker.py delete 3
"""

import argparse
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

DATA_FILE = Path("expenses.json")


def load_expenses(path=DATA_FILE):
    """Load expenses from a JSON file. Returns an empty list if none exists."""
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {path} is corrupted. Starting with an empty list.")
        return []


def save_expenses(expenses, path=DATA_FILE):
    """Save the list of expenses to a JSON file."""
    with path.open("w", encoding="utf-8") as f:
        json.dump(expenses, f, indent=2)


def add_expense(expenses, amount, category, note=""):
    """Add a new expense and return it. Raises ValueError for bad input."""
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("Amount must be a positive number.")
    if not category.strip():
        raise ValueError("Category cannot be empty.")

    next_id = max((e["id"] for e in expenses), default=0) + 1
    expense = {
        "id": next_id,
        "date": date.today().isoformat(),
        "amount": round(amount, 2),
        "category": category.strip().lower(),
        "note": note.strip(),
    }
    expenses.append(expense)
    return expense


def delete_expense(expenses, expense_id):
    """Delete an expense by ID. Returns True if deleted, False if not found."""
    for i, e in enumerate(expenses):
        if e["id"] == expense_id:
            del expenses[i]
            return True
    return False


def filter_by_category(expenses, category):
    """Return only the expenses in the given category."""
    return [e for e in expenses if e["category"] == category.strip().lower()]


def summarize(expenses):
    """Return (total, {category: subtotal}) for the given expenses."""
    by_category = defaultdict(float)
    for e in expenses:
        by_category[e["category"]] += e["amount"]
    total = sum(by_category.values())
    return round(total, 2), {c: round(v, 2) for c, v in by_category.items()}


def print_table(expenses):
    """Print expenses as a neat table."""
    if not expenses:
        print("No expenses found.")
        return
    print(f"{'ID':<4} {'Date':<11} {'Amount':>10}  {'Category':<12} Note")
    print("-" * 60)
    for e in expenses:
        print(
            f"{e['id']:<4} {e['date']:<11} {e['amount']:>10.2f}  "
            f"{e['category']:<12} {e['note']}"
        )


def print_summary(expenses):
    """Print total spending and a per-category breakdown."""
    if not expenses:
        print("No expenses to summarize.")
        return
    total, by_category = summarize(expenses)
    print(f"Total spent: {total:.2f}\n")
    print("By category:")
    for category, subtotal in sorted(by_category.items(), key=lambda x: -x[1]):
        percent = subtotal / total * 100
        bar = "#" * int(percent // 5)
        print(f"  {category:<12} {subtotal:>10.2f}  {percent:5.1f}%  {bar}")


def build_parser():
    parser = argparse.ArgumentParser(description="Simple command-line expense tracker.")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add a new expense")
    add.add_argument("amount", type=float, help="Amount spent")
    add.add_argument("category", help="Category, e.g. food, travel, bills")
    add.add_argument("note", nargs="?", default="", help="Optional note")

    lst = sub.add_parser("list", help="List expenses")
    lst.add_argument("--category", help="Show only this category")

    sub.add_parser("summary", help="Show totals by category")

    delete = sub.add_parser("delete", help="Delete an expense by ID")
    delete.add_argument("id", type=int, help="ID of the expense to delete")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    expenses = load_expenses()

    if args.command == "add":
        try:
            e = add_expense(expenses, args.amount, args.category, args.note)
        except ValueError as err:
            print(f"Error: {err}")
            return 1
        save_expenses(expenses)
        print(f"Added expense #{e['id']}: {e['amount']:.2f} on {e['category']}")

    elif args.command == "list":
        shown = (
            filter_by_category(expenses, args.category) if args.category else expenses
        )
        print_table(shown)

    elif args.command == "summary":
        print_summary(expenses)

    elif args.command == "delete":
        if delete_expense(expenses, args.id):
            save_expenses(expenses)
            print(f"Deleted expense #{args.id}")
        else:
            print(f"Error: no expense with ID {args.id}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
