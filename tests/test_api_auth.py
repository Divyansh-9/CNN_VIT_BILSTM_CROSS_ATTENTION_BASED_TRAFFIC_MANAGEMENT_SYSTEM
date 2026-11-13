"""D9: every HTTP write needs the bearer token; reads stay open.

NFR-12 as amended to ADR-008: a shared secret, here `STMS_API_TOKEN`, carried
as `Authorization: Bearer <token>` on every POST. With no token configured, no
write is accepted. GET endpoints and the dashboard stay open for reading. The
token never appears in a response, a log or a repr.

`conftest.py` configures a synthetic token for every test; the tests of the
unconfigured server delete it.
"""

from __future__ import annotations

import logging
import os

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from contracts.mqtt import (CongestionClass, CongestionPrediction,  # noqa: E402
                            CountForecast)

WRONG = "wrong-value-that-must-not-be-echoed"


@pytest.fixture
def canary():
    """The synthetic write token conftest.py configures for every test."""
    return os.environ["STMS_API_TOKEN"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    import server.app as server

    monkeypatch.setattr(server, "DATABASE", tmp_path / "auth.sqlite")
    server.guards.clear()
    return server


def writes():
    """One valid request per POST route."""
    prediction = CongestionPrediction(
        predictions={a: CongestionClass.LOW for a in "NSEW"},
        confidences={a: 0.76 for a in "NSEW"}, gate_value=None,
        model="persistence@2431c6641b9c").encode()
    forecast = CountForecast(counts={a: 1.5 for a in "NSEW"},
                             model="ridge@73532968dcf2").encode()
    text = {"content-type": "text/plain"}
    return [
        ("/observation", {"json": {"intersection_id": "j1",
                                   "counts": {"N": 3, "S": 1, "E": 0, "W": 2}}}),
        ("/prediction/j1", {"content": prediction, "headers": text}),
        ("/count_forecast/j1", {"content": forecast, "headers": text}),
    ]


def post(client, path, kwargs, auth=None):
    kwargs = dict(kwargs)
    headers = dict(kwargs.pop("headers", {}))
    if auth is not None:
        headers["Authorization"] = auth
    return client.post(path, headers=headers, **kwargs)


ROUTES = [path for path, _ in writes()]


@pytest.mark.parametrize("route", ROUTES)
def test_a_write_without_a_token_is_refused(app, route):
    kwargs = dict(writes())[route]
    response = post(TestClient(app.app), route, kwargs)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": app.WRITE_REFUSED}


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("template", ["Bearer {wrong}", "Basic {c}", "Bearer", "Bearer ",
                                      "{c}", "bearer{c}"])
def test_a_wrong_or_malformed_token_is_refused_without_echo(app, route, template, canary):
    auth = template.format(c=canary, wrong=WRONG)
    kwargs = dict(writes())[route]
    response = post(TestClient(app.app), route, kwargs, auth=auth)
    assert response.status_code == 401
    assert WRONG not in response.text and canary not in response.text


@pytest.mark.parametrize("route", ROUTES)
def test_the_right_token_writes_as_before(app, route, write_headers):
    kwargs = dict(writes())[route]
    response = post(TestClient(app.app), route, kwargs, auth=write_headers["Authorization"])
    assert response.status_code == 200, response.text


def test_the_scheme_is_case_insensitive(app, canary):
    path, kwargs = writes()[1]
    response = post(TestClient(app.app), path, kwargs, auth=f"bEaReR {canary}")
    assert response.status_code == 200


def test_an_unauthenticated_invalid_body_is_refused_before_it_is_validated(app):
    # 401, not 422: an unauthenticated caller learns nothing about validation.
    client = TestClient(app.app)
    assert client.post("/prediction/j1", content="not json",
                       headers={"content-type": "text/plain"}).status_code == 401
    assert client.post("/observation", json={"bogus": 1}).status_code == 401


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_with_no_token_configured_every_write_is_refused(app, monkeypatch, configured,
                                                         write_headers):
    if configured is None:
        monkeypatch.delenv(app.API_TOKEN_ENV, raising=False)
    else:
        monkeypatch.setenv(app.API_TOKEN_ENV, configured)
    for path, kwargs in writes():
        for auth in (write_headers["Authorization"], "Bearer ", None):
            assert post(TestClient(app.app), path, kwargs, auth=auth).status_code == 401


def test_reads_stay_open_without_a_token(app, write_headers):
    path, kwargs = writes()[1]
    assert post(TestClient(app.app), path, kwargs,
                auth=write_headers["Authorization"]).status_code == 200
    reader = TestClient(app.app)
    assert reader.get("/health").status_code == 200
    assert reader.get("/prediction/j1/latest").status_code == 200
    assert reader.get("/count_forecast/j1/latest").status_code == 404
    assert reader.get("/history/j1").status_code == 200
    assert reader.get("/evidence").status_code == 200


def test_the_start_up_warning_names_the_variable_and_nothing_else(app, monkeypatch, caplog,
                                                                  capsys):
    caplog.set_level(logging.WARNING, logger="server.app")
    with TestClient(app.app):
        pass
    assert not [r for r in caplog.records if app.API_TOKEN_ENV in r.getMessage()]
    monkeypatch.delenv(app.API_TOKEN_ENV)
    with TestClient(app.app):
        pass
    warned = [r.getMessage() for r in caplog.records if app.API_TOKEN_ENV in r.getMessage()]
    assert warned == [f"{app.API_TOKEN_ENV} is not set; every POST will be refused until it "
                      f"is (D9)"]


def test_no_token_appears_in_logs_output_or_responses(app, caplog, capsys, canary):
    caplog.set_level(logging.DEBUG)
    with TestClient(app.app) as client:
        for path, kwargs in writes():
            post(client, path, kwargs, auth=f"Bearer {WRONG}")
            post(client, path, kwargs, auth=f"Bearer {canary}")
    shown = caplog.text + "".join(capsys.readouterr())
    assert WRONG not in shown and canary not in shown


def test_the_comparison_is_constant_time(app):
    import inspect

    assert "hmac.compare_digest" in inspect.getsource(app.require_write_token)


def test_the_live_benchmark_transport_sends_the_token_from_the_environment(monkeypatch, canary):
    import urllib.request

    from scripts.benchmark_live import HttpTransport

    sent = []

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=None):
        sent.append(dict(request.header_items()))
        return Reply()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    transport = HttpTransport("http://127.0.0.1:8000", "j1")
    transport.publish("stms/j1/congestion/prediction", "{}", 0)
    assert sent[0]["Authorization"] == f"Bearer {canary}"


def test_verify_edge_writes_with_the_shared_header():
    import inspect

    import scripts.verify_edge as verify_edge

    source = inspect.getsource(verify_edge.main)
    assert "server.write_auth_header()" in source


def test_the_shared_header_reads_the_environment(app, monkeypatch, canary):
    assert app.write_auth_header() == {"Authorization": f"Bearer {canary}"}
    monkeypatch.setenv(app.API_TOKEN_ENV, "  spaced-canary  ")
    assert app.write_auth_header() == {"Authorization": "Bearer spaced-canary"}
