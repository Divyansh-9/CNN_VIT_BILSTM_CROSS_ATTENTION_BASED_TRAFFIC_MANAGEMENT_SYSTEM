"""Accounts and sign-in (server/auth.py), through the real server routes.

Registration, sign-in, sign-out, session expiry, direct access without a
session, password reset, guessing limits and forged requests. conftest.py gives
every test its own empty account store and a cheap scrypt cost.
"""

from __future__ import annotations

import email
import email.policy
import json
import os
import re
import sqlite3
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import server.auth as auth  # noqa: E402

GOOD = "Signal-Green-42!"
PERSON = {"full_name": "Asha Rao", "email": "asha@example.org", "username": "asha_r",
          "password": GOOD, "confirm_password": GOOD, "accept_terms": True}
PROTECTED = ["/evidence", "/sites", "/prediction/j1/latest", "/count_forecast/j1/history",
             "/vehicle_count/j1/history?window=1h", "/heartbeat/j1/latest", "/forecast_check/j1/recent",
             "/history/j1", "/docs", "/openapi.json"]


@pytest.fixture
def server(tmp_path, monkeypatch):
    import server.app as app

    monkeypatch.setattr(app, "DATABASE", tmp_path / "stms.sqlite")
    app.guards.clear()
    return app


@pytest.fixture
def client(server):
    return TestClient(server.app, base_url="http://127.0.0.1:8000")


def register(client, **changes):
    return client.post("/auth/register", json={**PERSON, **changes})


def login(client, identifier="asha_r", password=GOOD, remember=False):
    return client.post("/auth/login", json={"identifier": identifier, "password": password, "remember": remember})


# ------------------------------------------------------------------ registration ---

def test_register_then_sign_in_with_username_or_email(client):
    created = register(client)
    assert created.status_code == 201, created.text
    assert created.json()["user"] == {"id": 1, "full_name": "Asha Rao", "email": "asha@example.org",
                                      "username": "asha_r"}
    assert "set-cookie" not in created.headers           # registering does not sign in
    assert login(client).status_code == 200
    assert login(client, identifier="ASHA@example.org").status_code == 200


def test_the_password_is_stored_only_as_a_scrypt_hash(client):
    register(client)
    with sqlite3.connect(auth.database_path()) as db:
        stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert GOOD not in stored and stored.startswith("scrypt$")
    assert auth.verify_password(GOOD, stored) and not auth.verify_password(GOOD + "x", stored)
    assert stored != auth.hash_password(GOOD)              # salted


def test_production_cost_is_owasp_scrypt():
    # conftest lowers SCRYPT_N for speed; the module's own default must stay 2**17.
    source = Path(auth.__file__).read_text(encoding="utf-8")
    assert re.search(r"^SCRYPT_N = 2 \*\* 17$", source, re.M)
    assert (auth.SCRYPT_R, auth.SCRYPT_P) == (8, 1)


@pytest.mark.parametrize("changes, field", [
    ({"full_name": "A"}, "full_name"),
    ({"email": "not-an-email"}, "email"),
    ({"username": "1abc"}, "username"),
    ({"username": "ab"}, "username"),
    ({"password": "short1!A", "confirm_password": "short1!A"}, "password"),
    ({"password": "alllowercase1!", "confirm_password": "alllowercase1!"}, "password"),
    ({"password": "NoDigitsHere!!", "confirm_password": "NoDigitsHere!!"}, "password"),
    ({"password": "NoSymbols12345", "confirm_password": "NoSymbols12345"}, "password"),
    ({"password": "Password-12345", "confirm_password": "Password-12345"}, "password"),
    ({"password": "Asha_r-is-1-ok", "confirm_password": "Asha_r-is-1-ok"}, "password"),
    ({"confirm_password": "Signal-Green-43!"}, "confirm_password"),
    ({"accept_terms": False}, "accept_terms"),
    ({"accept_terms": "true"}, "accept_terms"),
])
def test_registration_refuses_each_bad_field_by_name(client, changes, field):
    refused = register(client, **changes)
    assert refused.status_code == 422
    assert field in refused.json()["errors"]
    with sqlite3.connect(auth.database_path()) as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_an_existing_email_or_username_is_refused_case_insensitively(client):
    assert register(client).status_code == 201
    again = register(client, email="ASHA@EXAMPLE.ORG", username="other_one")
    assert again.status_code == 422 and "email" in again.json()["errors"]
    again = register(client, email="new@example.org", username="ASHA_R")
    assert again.status_code == 422 and "username" in again.json()["errors"]


def test_no_password_is_echoed_in_any_answer(client):
    for response in (register(client), register(client), login(client, password="Wrong-Pass-99!"), login(client)):
        assert GOOD not in response.text and "Wrong-Pass-99!" not in response.text


# ------------------------------------------------------------------ the gate ---

def test_home_redirects_to_the_dashboard_without_a_session(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard/"


@pytest.mark.parametrize("path", PROTECTED)
def test_direct_access_without_signing_in_is_refused(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_a_session_opens_every_read_and_sign_out_closes_it(client):
    register(client)
    signed = login(client)
    cookie = signed.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Max-Age" not in cookie
    me = client.get("/auth/me")
    assert me.status_code == 200 and me.json()["user"]["username"] == "asha_r"
    assert client.get("/evidence").status_code != 401
    assert client.get("/sites").status_code == 200
    out = client.post("/auth/logout", json={})
    assert out.status_code == 200 and "Max-Age=0" in out.headers["set-cookie"]
    assert client.get("/auth/me").status_code == 401
    assert client.get("/sites").status_code == 401


def test_a_stolen_cookie_value_is_dead_after_sign_out(server):
    browser = TestClient(server.app)
    register(browser)
    login(browser)
    token = browser.cookies.get(auth.COOKIE)
    browser.post("/auth/logout", json={})
    replay = TestClient(server.app, cookies={auth.COOKIE: token})
    assert replay.get("/sites").status_code == 401


def test_a_session_cannot_write(client):
    register(client)
    login(client)
    refused = client.post("/observation", json={"intersection_id": "j1", "counts": {"N": 1, "S": 1, "E": 1, "W": 1}})
    assert refused.status_code == 401


def test_only_a_hash_of_the_session_is_stored(client):
    register(client)
    login(client)
    token = client.cookies.get(auth.COOKIE)
    with sqlite3.connect(auth.database_path()) as db:
        stored = [r[0] for r in db.execute("SELECT token_hash FROM sessions")]
    assert token not in stored and stored == [auth._token_hash(token)]


def test_remember_me_makes_a_lasting_cookie(client, monkeypatch):
    monkeypatch.setenv("STMS_REMEMBER_DAYS", "30")
    register(client)
    cookie = login(client, remember=True).headers["set-cookie"]
    assert f"Max-Age={30 * 86400}" in cookie
    assert client.get("/auth/me").json()["user"]["session"]["persistent"] is True


def test_secure_cookie_when_configured(client, monkeypatch):
    monkeypatch.setenv("STMS_COOKIE_SECURE", "1")
    register(client)
    assert "Secure" in login(client).headers["set-cookie"]


# ------------------------------------------------------------------ expiry ---

def _age_session(**columns):
    with sqlite3.connect(auth.database_path()) as db:
        for name, value in columns.items():
            db.execute(f"UPDATE sessions SET {name} = ?", (value,))  # noqa: S608 - test-only column names


def test_an_expired_session_is_refused_and_removed(client):
    register(client)
    login(client)
    _age_session(expires_at=time.time() - 1)
    assert client.get("/sites").status_code == 401
    with sqlite3.connect(auth.database_path()) as db:
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_an_idle_session_times_out_unless_remembered(client, monkeypatch):
    monkeypatch.setenv("STMS_SESSION_IDLE_MINUTES", "120")
    register(client)
    login(client)
    _age_session(last_seen=time.time() - 121 * 60)
    assert client.get("/auth/me").status_code == 401
    login(client, remember=True)
    _age_session(last_seen=time.time() - 121 * 60)
    assert client.get("/auth/me").status_code == 200


# ------------------------------------------------------------------ guessing ---

def test_five_wrong_passwords_lock_the_account_for_a_while(client):
    register(client)
    for _ in range(auth.MAX_ACCOUNT_FAILURES):
        assert login(client, password="Wrong-Pass-99!").status_code == 401
    locked = login(client)                                  # even the right password
    assert locked.status_code == 429 and int(locked.headers["retry-after"]) > 0
    assert "Try again in" in locked.json()["detail"]
    with sqlite3.connect(auth.database_path()) as db:
        db.execute("UPDATE login_failures SET at = at - ?", (auth.LOCK_WINDOW_S + 1,))
    assert login(client).status_code == 200


def test_unknown_and_wrong_answer_alike(client):
    register(client)
    unknown = login(client, identifier="nobody_here", password="Wrong-Pass-99!")
    wrong = login(client, password="Wrong-Pass-99!")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


# ------------------------------------------------------------------ forged requests ---

def test_a_cross_site_post_is_refused(client):
    refused = client.post("/auth/login", json={"identifier": "asha_r", "password": GOOD},
                          headers={"Origin": "http://evil.example"})
    assert refused.status_code == 403
    form = client.post("/auth/login", content=b"identifier=asha_r",
                       headers={"content-type": "application/x-www-form-urlencoded"})
    assert form.status_code == 415


def test_same_origin_post_is_accepted(client):
    register(client)
    assert client.post("/auth/login", json={"identifier": "asha_r", "password": GOOD},
                       headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200


# ------------------------------------------------------------------ password reset ---

def _outbox_text() -> str:
    """The one message in the outbox, decoded as a mail client would."""
    outbox = Path(os.environ["STMS_AUTH_OUTBOX"])
    messages = sorted(outbox.glob("*.eml"))
    assert len(messages) == 1
    message = email.message_from_bytes(messages[0].read_bytes(), policy=email.policy.default)
    return message.get_content()


def _outbox_link() -> str:
    return re.search(r"#reset/([A-Za-z0-9_-]+)", _outbox_text()).group(1)


def test_forgot_password_answers_the_same_for_any_address(client):
    register(client)
    known = client.post("/auth/forgot", json={"email": "asha@example.org"})
    unknown = client.post("/auth/forgot", json={"email": "nobody@example.org"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_reset_link_uses_the_configured_address_not_the_host_header(client, monkeypatch):
    monkeypatch.setenv("STMS_PUBLIC_URL", "https://stms.example.edu")
    register(client)
    client.post("/auth/forgot", json={"email": "asha@example.org"}, headers={"Host": "evil.example"})
    text = _outbox_text()
    assert "https://stms.example.edu/dashboard/#reset/" in text and "evil.example" not in text


def test_reset_changes_the_password_once_and_ends_every_session(server):
    browser = TestClient(server.app)
    register(browser)
    login(browser)
    browser.post("/auth/forgot", json={"email": "asha@example.org"})
    token = _outbox_link()
    with sqlite3.connect(auth.database_path()) as db:
        assert token not in json.dumps(db.execute("SELECT * FROM password_resets").fetchall())
    new = "Amber-Phase-77#"
    weak = browser.post("/auth/reset", json={"token": token, "password": "weak", "confirm_password": "weak"})
    assert weak.status_code == 422 and "password" in weak.json()["errors"]
    done = browser.post("/auth/reset", json={"token": token, "password": new, "confirm_password": new})
    assert done.status_code == 200
    assert browser.get("/auth/me").status_code == 401             # signed out everywhere
    assert login(browser).status_code == 401
    assert login(browser, password=new).status_code == 200
    again = browser.post("/auth/reset", json={"token": token, "password": new + "x", "confirm_password": new + "x"})
    assert again.status_code == 422 and "token" in again.json()["errors"]


def test_an_expired_reset_link_is_refused(client):
    register(client)
    client.post("/auth/forgot", json={"email": "asha@example.org"})
    token = _outbox_link()
    with sqlite3.connect(auth.database_path()) as db:
        db.execute("UPDATE password_resets SET expires_at = ?", (time.time() - 1,))
    new = "Amber-Phase-77#"
    refused = client.post("/auth/reset", json={"token": token, "password": new, "confirm_password": new})
    assert refused.status_code == 422 and "token" in refused.json()["errors"]
