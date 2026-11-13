"""D10: MQTT over TLS when a CA is configured, with mandatory verification.

These need no broker; `test_mosquitto_live.py` proves the same against a real
Mosquitto. TLS material is made fresh per run with `openssl`, and these tests
skip without it.
"""

from __future__ import annotations

import inspect
import ssl
from pathlib import Path

import pytest

pytest.importorskip("paho.mqtt")

from contracts.broker import (CA_FILE_ENV, TlsConfigError, ca_file_from_env,  # noqa: E402
                              client_tls_context)
from scripts.tls_material import make_ca, openssl  # noqa: E402

needs_openssl = pytest.mark.skipif(openssl() is None, reason="needs the openssl command")


@pytest.fixture(scope="module")
def ca(tmp_path_factory):
    if openssl() is None:
        pytest.skip("needs the openssl command")
    return make_ca(tmp_path_factory.mktemp("ca"), "trusted")[0]


def test_unset_or_empty_means_plain_tcp():
    assert ca_file_from_env({}) is None
    assert ca_file_from_env({CA_FILE_ENV: "  "}) is None


@pytest.mark.parametrize("kind", ["missing", "directory", "not a certificate", "empty"])
def test_an_unusable_ca_file_is_refused_not_ignored(tmp_path, kind):
    path = {"missing": tmp_path / "absent.pem", "directory": tmp_path,
            "not a certificate": tmp_path / "notes.pem", "empty": tmp_path / "empty.pem"}[kind]
    if kind == "not a certificate":
        path.write_text("this is not a certificate\n", encoding="utf-8")
    if kind == "empty":
        path.write_text("", encoding="utf-8")
    with pytest.raises(TlsConfigError) as refused:
        ca_file_from_env({CA_FILE_ENV: str(path)})
    message = str(refused.value)
    assert CA_FILE_ENV in message and "refusing to connect without TLS" in message
    assert str(path) not in message and path.name not in message


@needs_openssl
def test_a_real_ca_file_is_accepted(ca):
    assert ca_file_from_env({CA_FILE_ENV: str(ca)}) == ca


@needs_openssl
def test_the_context_always_verifies(ca):
    context = client_tls_context(ca)
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


@pytest.fixture
def tls_calls(monkeypatch):
    import paho.mqtt.client as mqtt

    calls = {"context": [], "insecure": []}
    original = mqtt.Client.tls_set_context

    def spy_context(self, context=None):
        calls["context"].append(context)
        return original(self, context)

    monkeypatch.setattr(mqtt.Client, "tls_set_context", spy_context)
    monkeypatch.setattr(mqtt.Client, "tls_insecure_set",
                        lambda self, value: calls["insecure"].append(value))
    return calls


@needs_openssl
@pytest.mark.parametrize("build", ["edge", "server"])
def test_each_client_uses_tls_only_when_given_a_ca_and_never_relaxes_it(build, ca, tls_calls):
    from edge.mqtt_transport import MqttTransport
    from server.mqtt_ingest import PredictionIngest

    make = {"edge": lambda c: MqttTransport(client_id="edge-x", ca_file=c),
            "server": lambda c: PredictionIngest(ca_file=c)}[build]
    plain = make(None)
    assert plain.tls is False and tls_calls["context"] == []
    secure = make(ca)
    assert secure.tls is True
    [context] = tls_calls["context"]
    assert context.verify_mode is ssl.CERT_REQUIRED and context.check_hostname
    assert tls_calls["insecure"] == []          # never called, so never set to True


def test_no_code_path_can_switch_verification_off():
    root = Path(__file__).resolve().parent.parent
    for rel in ("contracts/broker.py", "edge/mqtt_transport.py", "server/mqtt_ingest.py",
                "edge/run.py"):
        source = (root / rel).read_text(encoding="utf-8")
        for forbidden in ("tls_insecure_set(True)", "CERT_NONE", "check_hostname = False",
                          "check_hostname=False", "_create_unverified_context"):
            assert forbidden not in source, f"{rel} contains {forbidden}"


def test_the_ingest_refuses_an_unusable_ca_file_at_start_up(monkeypatch, tmp_path):
    from server import mqtt_ingest

    monkeypatch.delenv("STMS_MQTT_USERNAME", raising=False)
    monkeypatch.delenv("STMS_MQTT_PASSWORD", raising=False)
    monkeypatch.setenv(CA_FILE_ENV, str(tmp_path / "absent.pem"))
    with pytest.raises(SystemExit) as stop:
        mqtt_ingest.main(["--port", "1"])
    assert CA_FILE_ENV in str(stop.value) and "absent.pem" not in str(stop.value)


def test_the_context_helper_is_the_only_tls_entry_point():
    import edge.mqtt_transport as transport
    import server.mqtt_ingest as ingest

    for module in (transport, ingest):
        source = inspect.getsource(module)
        assert "tls_set_context(client_tls_context(" in source
        assert "tls_set(" not in source.replace("tls_set_context(", "")
