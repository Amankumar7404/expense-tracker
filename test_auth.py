import jwt
import pytest

from app import create_app
from auth import (
    ALGORITHM,
    COOKIE_NAME,
    create_token,
    decode_token,
    register_user,
    verify_user,
)
from tracker import load_expenses

SECRET = "s" * 40


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "e.json", tmp_path / "u.json", jwt_secret=SECRET)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, username="alice", password="password123"):
    return client.post(
        "/register",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def api_token(client, username="alice", password="password123"):
    response = client.post(
        "/api/login", json={"username": username, "password": password}
    )
    return response.get_json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- token functions ----------


def test_token_round_trip():
    assert decode_token(create_token("alice", SECRET), SECRET) == "alice"


def test_expired_token_is_rejected():
    assert decode_token(create_token("alice", SECRET, minutes=-1), SECRET) is None


def test_token_signed_with_other_secret_is_rejected():
    assert decode_token(create_token("alice", "x" * 40), SECRET) is None


def test_tampered_token_is_rejected():
    token = create_token("alice", SECRET)
    header, payload, signature = token.split(".")
    forged = ".".join([header, payload, signature[:-2] + "AA"])
    assert decode_token(forged, SECRET) is None


def test_unsigned_alg_none_token_is_rejected():
    forged = jwt.encode({"sub": "alice", "exp": 9999999999}, key=None, algorithm="none")
    assert decode_token(forged, SECRET) is None


def test_token_without_expiry_is_rejected():
    token = jwt.encode({"sub": "alice"}, SECRET, algorithm=ALGORITHM)
    assert decode_token(token, SECRET) is None


def test_garbage_token_is_rejected():
    assert decode_token("not-a-token", SECRET) is None
    assert decode_token("", SECRET) is None


# ---------- users and passwords ----------


def test_register_user_hashes_password():
    users = {}
    register_user(users, "Alice", "password123")
    assert "alice" in users  # usernames are lowercased
    assert users["alice"]["password_hash"] != "password123"


@pytest.mark.parametrize(
    "username, password",
    [
        ("ab", "password123"),
        ("bad name!", "password123"),
        ("alice", "short"),
        ("alice", "x" * 200),
    ],
)
def test_register_user_rejects_bad_input(username, password):
    with pytest.raises(ValueError):
        register_user({}, username, password)


def test_register_user_rejects_duplicate():
    users = {}
    register_user(users, "alice", "password123")
    with pytest.raises(ValueError):
        register_user(users, "ALICE", "password456")


def test_verify_user():
    users = {}
    register_user(users, "alice", "password123")
    assert verify_user(users, "alice", "password123") == "alice"
    assert verify_user(users, "alice", "wrong-password") is None
    assert verify_user(users, "nobody", "password123") is None


# ---------- web pages ----------


def test_pages_redirect_to_login_without_token(client):
    for path in ["/"]:
        response = client.get(path)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
    assert (
        client.post("/add", data={"amount": "5", "category": "food"}).status_code == 302
    )
    assert client.post("/delete/1").status_code == 302


def test_register_sets_httponly_cookie_and_logs_in(client):
    response = client.post(
        "/register", data={"username": "alice", "password": "password123"}
    )
    cookie_header = response.headers["Set-Cookie"]
    assert COOKIE_NAME in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=Lax" in cookie_header
    assert client.get("/").status_code == 200


def test_duplicate_registration_shows_error(client):
    register(client)
    other = client.application.test_client()
    assert b"already taken" in register(other).data


def test_login_with_wrong_password_fails(client, app):
    register(client)
    other = app.test_client()
    response = other.post(
        "/login", data={"username": "alice", "password": "nope"}, follow_redirects=True
    )
    assert b"Wrong username or password" in response.data
    assert other.get("/").status_code == 302


def test_login_with_right_password_works(client, app):
    register(client)
    other = app.test_client()
    other.post("/login", data={"username": "alice", "password": "password123"})
    assert other.get("/").status_code == 200


def test_logout_clears_access(client):
    register(client)
    client.post("/logout")
    assert client.get("/").status_code == 302


def test_forged_cookie_is_rejected(client):
    client.set_cookie(COOKIE_NAME, create_token("alice", "x" * 40))
    assert client.get("/").status_code == 302


def test_expired_cookie_is_rejected(client):
    client.set_cookie(COOKIE_NAME, create_token("alice", SECRET, minutes=-1))
    assert client.get("/").status_code == 302


def test_users_only_see_their_own_expenses(app):
    alice, bob = app.test_client(), app.test_client()
    register(alice, "alice")
    register(bob, "bobby")
    alice.post(
        "/add", data={"amount": "10", "category": "food", "note": "alice secret"}
    )
    assert b"alice secret" in alice.get("/").data
    assert b"alice secret" not in bob.get("/").data


def test_user_cannot_delete_someone_elses_expense(app):
    alice, bob = app.test_client(), app.test_client()
    register(alice, "alice")
    register(bob, "bobby")
    alice.post("/add", data={"amount": "10", "category": "food"})
    response = bob.post("/delete/1", follow_redirects=True)
    assert b"No expense with ID 1" in response.data
    assert len(load_expenses(app.config["DATA_FILE"])) == 1


# ---------- JSON API ----------


def test_api_login_returns_token(client):
    register(client)
    response = client.post(
        "/api/login", json={"username": "alice", "password": "password123"}
    )
    body = response.get_json()
    assert response.status_code == 200
    assert body["token_type"] == "Bearer"
    assert decode_token(body["access_token"], SECRET) == "alice"


def test_api_login_rejects_bad_credentials(client):
    register(client)
    response = client.post(
        "/api/login", json={"username": "alice", "password": "wrong"}
    )
    assert response.status_code == 401


def test_api_login_rejects_non_json(client):
    assert client.post("/api/login", data="hello").status_code == 400


def test_api_requires_token(client):
    assert client.get("/api/expenses").status_code == 401
    assert (
        client.post("/api/expenses", json={"amount": 5, "category": "food"}).status_code
        == 401
    )
    assert client.delete("/api/expenses/1").status_code == 401
    assert client.get("/api/expenses", headers=bearer("garbage")).status_code == 401


def test_api_ignores_login_cookie(client):
    register(client)  # the browser cookie is set now
    assert client.get("/api/expenses").status_code == 401


def test_api_create_list_delete(client):
    register(client)
    token = api_token(client)

    created = client.post(
        "/api/expenses",
        json={"amount": 12.5, "category": "Food", "note": "Tea"},
        headers=bearer(token),
    )
    assert created.status_code == 201
    assert created.get_json()["owner"] == "alice"

    listed = client.get("/api/expenses", headers=bearer(token)).get_json()["expenses"]
    assert [e["note"] for e in listed] == ["Tea"]

    assert client.delete("/api/expenses/1", headers=bearer(token)).status_code == 204
    assert (
        client.get("/api/expenses", headers=bearer(token)).get_json()["expenses"] == []
    )


def test_api_validation_errors(client):
    register(client)
    headers = bearer(api_token(client))
    assert (
        client.post(
            "/api/expenses", json={"category": "x"}, headers=headers
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/expenses", json={"amount": "abc", "category": "x"}, headers=headers
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/expenses", json={"amount": -1, "category": "x"}, headers=headers
        ).status_code
        == 400
    )
    assert (
        client.post("/api/expenses", json={"amount": 5}, headers=headers).status_code
        == 400
    )


def test_api_users_are_isolated(app):
    alice, bob = app.test_client(), app.test_client()
    register(alice, "alice")
    register(bob, "bobby")
    alice_headers = bearer(api_token(alice, "alice"))
    bob_headers = bearer(api_token(bob, "bobby"))

    alice.post(
        "/api/expenses", json={"amount": 5, "category": "food"}, headers=alice_headers
    )
    assert bob.get("/api/expenses", headers=bob_headers).get_json()["expenses"] == []
    assert bob.delete("/api/expenses/1", headers=bob_headers).status_code == 404
