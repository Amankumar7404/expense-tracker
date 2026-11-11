"""Expense Tracker - Flask web app with JWT authentication.

Reuses the logic from tracker.py and adds:
  * register / login / logout pages (JWT stored in an HttpOnly cookie)
  * per-user expenses (you only ever see your own)
  * a small JSON API that uses the token in an Authorization header

Run with:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""

import os
from pathlib import Path

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from auth import (
    TOKEN_MINUTES,
    clear_login_cookie,
    create_token,
    load_users,
    login_required,
    register_user,
    save_users,
    set_login_cookie,
    token_required,
    verify_user,
)
from tracker import (
    add_expense,
    delete_expense,
    filter_by_category,
    filter_by_owner,
    load_expenses,
    save_expenses,
    summarize,
)

DEV_SECRET = "dev-only-secret-change-me-before-deploying-0123456789"


def create_app(data_file="expenses.json", users_file="users.json", jwt_secret=None):
    """Application factory: lets tests use temporary files and a test secret."""
    app = Flask(__name__)
    secret = jwt_secret or os.environ.get("JWT_SECRET", DEV_SECRET)
    app.config["SECRET_KEY"] = secret  # signs flash messages
    app.config["JWT_SECRET"] = secret  # signs login tokens
    app.config["DATA_FILE"] = Path(data_file)
    app.config["USERS_FILE"] = Path(users_file)
    # Set COOKIE_SECURE=1 when the site is served over HTTPS.
    app.config["COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE") == "1"

    # ---------------- web pages: accounts ----------------

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET":
            return render_template("register.html")

        users = load_users(app.config["USERS_FILE"])
        try:
            username = register_user(
                users, request.form.get("username"), request.form.get("password")
            )
        except ValueError as err:
            flash(str(err), "error")
            return redirect(url_for("register"))

        save_users(users, app.config["USERS_FILE"])
        token = create_token(username, app.config["JWT_SECRET"])
        flash(
            f"Welcome, {username.capitalize()}! Your account has been created.",
            "success",
        )
        return set_login_cookie(redirect(url_for("index")), token)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html")

        users = load_users(app.config["USERS_FILE"])
        username = verify_user(
            users, request.form.get("username"), request.form.get("password")
        )
        if username is None:
            flash("Wrong username or password.", "error")
            return redirect(url_for("login"))

        token = create_token(username, app.config["JWT_SECRET"])
        return set_login_cookie(redirect(url_for("index")), token)

    @app.route("/logout", methods=["POST"])
    def logout():
        flash("You have been logged out.", "success")
        return clear_login_cookie(redirect(url_for("login")))

    # ---------------- web pages: expenses (login required) ----------------

    @app.route("/")
    @login_required
    def index():
        mine = filter_by_owner(load_expenses(app.config["DATA_FILE"]), g.user)
        selected = request.args.get("category", "").strip().lower()

        shown = filter_by_category(mine, selected) if selected else mine
        shown = sorted(shown, key=lambda e: e["id"], reverse=True)  # newest first

        total, by_category = summarize(mine)
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
            username=g.user,
            expenses=shown,
            total=total,
            breakdown=breakdown,
            categories=sorted(by_category),
            selected=selected,
        )

    @app.route("/add", methods=["POST"])
    @login_required
    def add():
        expenses = load_expenses(app.config["DATA_FILE"])
        try:
            amount = float(request.form.get("amount", ""))
            expense = add_expense(
                expenses,
                amount,
                request.form.get("category", ""),
                request.form.get("note", ""),
                owner=g.user,
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
    @login_required
    def delete(expense_id):
        expenses = load_expenses(app.config["DATA_FILE"])
        if delete_expense(expenses, expense_id, owner=g.user):
            save_expenses(expenses, app.config["DATA_FILE"])
            flash(f"Deleted expense #{expense_id}.", "success")
        else:
            flash(f"No expense with ID {expense_id}.", "error")
        return redirect(url_for("index"))

    # ---------------- JSON API (Bearer token) ----------------

    @app.route("/api/login", methods=["POST"])
    def api_login():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON body with username and password."), 400

        users = load_users(app.config["USERS_FILE"])
        username = verify_user(users, data.get("username"), data.get("password"))
        if username is None:
            return jsonify(error="Wrong username or password."), 401

        token = create_token(username, app.config["JWT_SECRET"])
        return jsonify(
            access_token=token, token_type="Bearer", expires_in=TOKEN_MINUTES * 60
        )

    @app.route("/api/expenses", methods=["GET"])
    @token_required
    def api_list():
        mine = filter_by_owner(load_expenses(app.config["DATA_FILE"]), g.user)
        return jsonify(expenses=mine)

    @app.route("/api/expenses", methods=["POST"])
    @token_required
    def api_add():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON body."), 400

        try:
            amount = float(data.get("amount"))
        except (TypeError, ValueError):
            return jsonify(error="Amount must be a number."), 400

        expenses = load_expenses(app.config["DATA_FILE"])
        try:
            expense = add_expense(
                expenses,
                amount,
                str(data.get("category", "")),
                str(data.get("note", "")),
                owner=g.user,
            )
        except ValueError as err:
            return jsonify(error=str(err)), 400

        save_expenses(expenses, app.config["DATA_FILE"])
        return jsonify(expense), 201

    @app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
    @token_required
    def api_delete(expense_id):
        expenses = load_expenses(app.config["DATA_FILE"])
        if not delete_expense(expenses, expense_id, owner=g.user):
            return jsonify(error=f"No expense with ID {expense_id}."), 404
        save_expenses(expenses, app.config["DATA_FILE"])
        return "", 204

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
