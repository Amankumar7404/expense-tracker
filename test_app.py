import pytest

from app import create_app
from tracker import load_expenses


@pytest.fixture
def client_and_file(tmp_path):
    """A test client that is already registered and logged in."""
    data_file = tmp_path / "test_expenses.json"
    app = create_app(data_file, tmp_path / "test_users.json", jwt_secret="t" * 40)
    app.config["TESTING"] = True
    client = app.test_client()
    client.post(
        "/register",
        data={"username": "tester", "password": "password123"},
    )
    return client, data_file


def add(client, amount, category, note=""):
    return client.post(
        "/add",
        data={"amount": amount, "category": category, "note": note},
        follow_redirects=True,
    )


def test_home_page_loads_empty(client_and_file):
    client, _ = client_and_file
    response = client.get("/")
    assert response.status_code == 200
    assert b"No expenses found" in response.data
    assert b"<strong>Tester</strong>" in response.data


def test_add_expense_shows_on_page_and_is_saved(client_and_file):
    client, data_file = client_and_file
    response = add(client, "250", "Food", "Lunch")
    assert b"Added 250.00 to food" in response.data
    assert b"Lunch" in response.data
    saved = load_expenses(data_file)
    assert len(saved) == 1
    assert saved[0]["owner"] == "tester"


def test_invalid_amount_shows_error(client_and_file):
    client, data_file = client_and_file
    assert b"valid number" in add(client, "abc", "food").data
    assert b"positive number" in add(client, "-5", "food").data
    assert b"positive number" in add(client, "nan", "food").data
    assert not data_file.exists() or load_expenses(data_file) == []


def test_empty_category_shows_error(client_and_file):
    client, _ = client_and_file
    assert b"Category cannot be empty" in add(client, "10", "   ").data


def test_filter_by_category(client_and_file):
    client, _ = client_and_file
    add(client, "10", "food", "Snack")
    add(client, "20", "travel", "Bus ticket")
    page = client.get("/?category=travel").data
    assert b"Bus ticket" in page
    assert b"Snack" not in page


def test_delete_expense(client_and_file):
    client, data_file = client_and_file
    add(client, "10", "food")
    response = client.post("/delete/1", follow_redirects=True)
    assert b"Deleted expense #1" in response.data
    assert load_expenses(data_file) == []


def test_delete_missing_expense_shows_error(client_and_file):
    client, _ = client_and_file
    response = client.post("/delete/99", follow_redirects=True)
    assert b"No expense with ID 99" in response.data


def test_summary_shows_total(client_and_file):
    client, _ = client_and_file
    add(client, "10.50", "food")
    add(client, "4.50", "food")
    add(client, "20", "travel")
    assert b"35.00" in client.get("/").data


def test_html_in_note_is_escaped(client_and_file):
    client, _ = client_and_file
    add(client, "10", "food", "<script>alert(1)</script>")
    page = client.get("/").data
    assert b"<script>alert(1)</script>" not in page
    assert b"&lt;script&gt;" in page
