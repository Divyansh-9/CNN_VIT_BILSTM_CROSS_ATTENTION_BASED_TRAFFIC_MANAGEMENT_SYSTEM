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


@pytest.fixture
def write_headers():
    """The header a legitimate writer sends."""
    return {"Authorization": f"Bearer {WRITE_CANARY}"}
