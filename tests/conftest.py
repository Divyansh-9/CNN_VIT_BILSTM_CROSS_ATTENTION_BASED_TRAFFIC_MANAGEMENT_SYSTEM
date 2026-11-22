"""Shared pytest configuration."""


def pytest_addoption(parser):
    parser.addoption(
        "--run-pretrained",
        action="store_true",
        default=False,
        help="run tests that download real backbone weights (~200 MB)",
    )


import pytest  # noqa: E402

#: A synthetic canary for the server's write check (D9), not a credential: if it
#: ever appears in output, something leaked.
WRITE_CANARY = "canary-write-value-for-tests"


@pytest.fixture(autouse=True)
def api_write_configured(monkeypatch):
    """Every test runs against a server with a write token configured, as a
    deployment must be. Tests of the unconfigured case delete it themselves."""
    monkeypatch.setenv("STMS_API_TOKEN", WRITE_CANARY)


@pytest.fixture(autouse=True)
def accounts_isolated(monkeypatch, tmp_path_factory):
    """Every test gets its own empty account store and outbox, never data/server/,
    and a cheap scrypt cost so hashing does not dominate the suite. The
    production cost is pinned by tests/test_auth.py, not left to this fixture."""
    folder = tmp_path_factory.mktemp("accounts")
    monkeypatch.setenv("STMS_AUTH_DB", str(folder / "auth.sqlite"))
    monkeypatch.setenv("STMS_AUTH_OUTBOX", str(folder / "outbox"))
    monkeypatch.delenv("STMS_SMTP_HOST", raising=False)
    try:
        import server.auth as auth
    except ImportError:
        return
    monkeypatch.setattr(auth, "SCRYPT_N", 2 ** 10)


@pytest.fixture
def session_cookie(accounts_isolated):
    """A `Cookie` header value for a signed-in person, made through server/auth.py."""
    import server.auth as auth

    password = "Signal-Green-42!"
    auth.register({"full_name": "Test Person", "email": "person@example.org", "username": "test_person",
                   "password": password, "confirm_password": password, "accept_terms": True})
    signed = auth.sign_in({"identifier": "test_person", "password": password})
    assert signed.token, signed.error
    return f"{auth.COOKIE}={signed.token}"


@pytest.fixture
def write_headers():
    """The header a legitimate writer sends."""
    return {"Authorization": f"Bearer {WRITE_CANARY}"}
