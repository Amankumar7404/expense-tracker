"""Authentication helpers: users, password hashing, and JWT tokens.

How login works:
1. The user sends a username and password.
2. The server checks the password against a stored hash.
3. If it matches, the server signs a JWT (a token) containing the username
   and an expiry time, and sends it back.
4. On later requests the client sends the token back. The server verifies the
   signature and expiry, so it does not need to remember who is logged in.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import jwt
from flask import current_app, flash, g, jsonify, redirect, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

ALGORITHM = "HS256"
COOKIE_NAME = "access_token"
TOKEN_MINUTES = 60

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Used so that a login for an unknown username takes about as long as a
# login with a wrong password (prevents guessing which usernames exist).
_DUMMY_HASH = generate_password_hash("not-a-real-password")


# ---------- users (stored in a JSON file) ----------


def load_users(path):
    """Load {username: {"password_hash": ...}} from a JSON file."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_users(users, path):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def register_user(users, username, password):
    """Add a user to the dict and return the cleaned username.

    Raises ValueError with a readable message for invalid input.
    """
    username = (username or "").strip().lower()
    password = password or ""

    if not USERNAME_RE.match(username):
        raise ValueError(
            "Username must be 3-20 characters: letters, numbers or underscores."
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")
    if username in users:
        raise ValueError("That username is already taken.")

    users[username] = {"password_hash": generate_password_hash(password)}
    return username


def verify_user(users, username, password):
    """Return the cleaned username if the credentials are right, else None."""
    username = (username or "").strip().lower()
    user = users.get(username)
    stored_hash = user["password_hash"] if user else _DUMMY_HASH
    password_ok = check_password_hash(stored_hash, password or "")
    return username if (user and password_ok) else None


# ---------- JWT ----------


def create_token(username, secret, minutes=TOKEN_MINUTES):
    """Create a signed token that expires after `minutes`."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token, secret):
    """Return the username inside a valid token, or None if it is not valid."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],  # never trust the algorithm named in the token
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    return payload["sub"]


# ---------- request helpers ----------


def _token_from_cookie():
    return request.cookies.get(COOKIE_NAME)


def _token_from_header():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token.strip()
    return None


def set_login_cookie(response, token):
    """Attach the token to a response as a cookie JavaScript cannot read."""
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=TOKEN_MINUTES * 60,
        httponly=True,  # not readable by page scripts, which limits XSS damage
        samesite="Lax",  # not sent on cross-site POSTs, which limits CSRF
        secure=current_app.config["COOKIE_SECURE"],  # True when served over HTTPS
    )
    return response


def clear_login_cookie(response):
    response.delete_cookie(COOKIE_NAME)
    return response


def login_required(view):
    """Protect a web page. Reads the token from the cookie."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        username = decode_token(
            _token_from_cookie() or "", current_app.config["JWT_SECRET"]
        )
        if username is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        g.user = username
        return view(*args, **kwargs)

    return wrapper


def token_required(view):
    """Protect an API endpoint. Reads the token from the Authorization header.

    API routes ignore the cookie on purpose, so a malicious website cannot
    make a logged-in browser call them.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        username = decode_token(
            _token_from_header() or "", current_app.config["JWT_SECRET"]
        )
        if username is None:
            response = jsonify(error="Missing, invalid or expired token.")
            response.status_code = 401
            response.headers["WWW-Authenticate"] = "Bearer"
            return response
        g.user = username
        return view(*args, **kwargs)

    return wrapper
