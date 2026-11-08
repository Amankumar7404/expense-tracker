"""Expense Tracker - Flask web app.

Reuses the logic from tracker.py (add, delete, filter, summarize) and
adds a browser interface on top of it.

Run with:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""

import os
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from tracker import (
    add_expense,
    delete_expense,
    filter_by_category,
    load_expenses,
    save_expenses,
    summarize,
)


def create_app(data_file="expenses.json"):
    """Application factory: lets tests use a temporary data file."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    app.config["DATA_FILE"] = Path(data_file)

    @app.route("/")
    def index():
        expenses = load_expenses(app.config["DATA_FILE"])
        selected = request.args.get("category", "").strip().lower()

        shown = filter_by_category(expenses, selected) if selected else expenses
        shown = sorted(shown, key=lambda e: e["id"], reverse=True)  # newest first

        total, by_category = summarize(expenses)
        breakdown = [
            {
                "category": category,
                "amount": amount,
                "percent": round(amount / total * 100, 1) if total else 0,
            }
            for category, amount in sorted(by_category.items(), key=lambda x: -x[1])
        ]

        return render_template(
            "index.html",
            expenses=shown,
            total=total,
            breakdown=breakdown,
            categories=sorted(by_category),
            selected=selected,
        )

    @app.route("/add", methods=["POST"])
    def add():
        expenses = load_expenses(app.config["DATA_FILE"])
        try:
            amount = float(request.form.get("amount", ""))
            expense = add_expense(
                expenses,
                amount,
                request.form.get("category", ""),
                request.form.get("note", ""),
            )
        except ValueError as err:
            message = str(err)
            if message.startswith("could not convert"):
                message = "Please enter a valid number for the amount."
            flash(message, "error")
        else:
            save_expenses(expenses, app.config["DATA_FILE"])
            flash(f"Added {expense['amount']:.2f} to {expense['category']}.", "success")
        return redirect(url_for("index"))

    @app.route("/delete/<int:expense_id>", methods=["POST"])
    def delete(expense_id):
        expenses = load_expenses(app.config["DATA_FILE"])
        if delete_expense(expenses, expense_id):
            save_expenses(expenses, app.config["DATA_FILE"])
            flash(f"Deleted expense #{expense_id}.", "success")
        else:
            flash(f"No expense with ID {expense_id}.", "error")
        return redirect(url_for("index"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
