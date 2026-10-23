"""NFR-11 and D10 against a real Mosquitto: authentication, reconnection, TLS.

    MOSQUITTO_EXE=<path to mosquitto.exe> pytest tests/test_mosquitto_live.py

`test_mqtt_live.py` proves the clients against amqtt. This file proves them
against Mosquitto, the broker PRD §17 names. It skips without `MOSQUITTO_EXE`,
and the TLS tests also skip without the `openssl` command.

Every broker here runs in the foreground on a free local port, with a
configuration, password file, certificates, keys and log written to a
temporary directory. Passwords are random per run and go into the password
file through `mosquitto_passwd -U`, never on a command line. The CA material
is made fresh per run, and nothing is committed.
"""

from __future__ import annotations

import logging
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("paho.mqtt")

from contracts.broker import Credentials  # noqa: E402
from scripts.tls_material import make_ca, make_leaf, make_self_signed, openssl  # noqa: E402

MOSQUITTO = os.environ.get("MOSQUITTO_EXE")
pytestmark = pytest.mark.skipif(not MOSQUITTO or not Path(MOSQUITTO).is_file(),
                                reason="no Mosquitto; set MOSQUITTO_EXE")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_port(port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.1)
    return False


def wait_until(predicate, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return False


class Broker:
    """One Mosquitto process: authenticated, optionally TLS."""

    def __init__(self, directory: Path, users: dict[str, str], tls: tuple[Path, Path] | None):
        self.directory, self.port, self.process = directory, free_port(), None
        passwords = directory / "passwords"
        passwords.write_text("".join(f"{u}:{p}\n" for u, p in users.items()), encoding="utf-8")
        # Hash the plain file in place, so no password is ever on a command line.
        subprocess.run([str(Path(MOSQUITTO).with_name("mosquitto_passwd.exe"
                                                       if os.name == "nt" else "mosquitto_passwd")),
                        "-U", str(passwords)], check=True, capture_output=True, timeout=60)
        self.log = directory / "mosquitto.log"
        lines = [f"listener {self.port} 127.0.0.1", "allow_anonymous false",
                 f"password_file {passwords.as_posix()}", "persistence false",
                 f"log_dest file {self.log.as_posix()}"]
        if tls is not None:
            lines += [f"certfile {tls[0].as_posix()}", f"keyfile {tls[1].as_posix()}",
                      "tls_version tlsv1.2"]
        self.config = directory / "mosquitto.conf"
        self.config.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def start(self) -> "Broker":
        self.process = subprocess.Popen([MOSQUITTO, "-c", str(self.config)],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert wait_port(self.port), "mosquitto did not start"
        return self

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)


@pytest.fixture
def users():
    return {"edge-test": secrets.token_urlsafe(18), "ingest-test": secrets.token_urlsafe(18)}


@pytest.fixture
def plain_broker(tmp_path, users):
    broker = Broker(tmp_path, users, tls=None).start()
    yield broker
    broker.stop()


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    if openssl() is None:
        pytest.skip("needs the openssl command")
    d = tmp_path_factory.mktemp("pki")
    trusted = make_ca(d, "trusted")
    return {
        "trusted_ca": trusted[0],
        "wrong_ca": make_ca(d, "wrong")[0],
        "good": make_leaf(d, "good", trusted, "DNS:localhost, IP:127.0.0.1"),
        "wrong_name": make_leaf(d, "wrongname", trusted, "DNS:wronghost.example"),
        "self_signed": make_self_signed(d, "selfsigned", "DNS:localhost, IP:127.0.0.1"),
    }


def tls_broker(tmp_path, users, cert):
    return Broker(tmp_path, users, tls=cert).start()


def edge(port, credentials=None, ca_file=None, client_id="edge-live"):
    from edge.mqtt_transport import MqttTransport

    return MqttTransport(port=port, client_id=client_id, credentials=credentials,
                         ca_file=ca_file)


def ingest(port, credentials=None, ca_file=None):
    from server.mqtt_ingest import PredictionIngest

    return PredictionIngest(port=port, client_id="ingest-live", credentials=credentials,
                            ca_file=ca_file)


def outcome(client, wait_s=4.0):
    try:
        accepted = client.start(wait_s=wait_s)
        return accepted, client.connect_refused
    finally:
        client.stop()


# ---- authentication on a real Mosquitto (NFR-11) ---------------------------

@pytest.mark.parametrize("who", ["edge", "ingest"])
def test_mosquitto_accepts_the_right_credentials(plain_broker, users, who):
    make = edge if who == "edge" else ingest
    user = "edge-test" if who == "edge" else "ingest-test"
    accepted, refused = outcome(make(plain_broker.port, Credentials(user, users[user])))
    assert accepted and refused is None


@pytest.mark.parametrize("who", ["edge", "ingest"])
@pytest.mark.parametrize("case", ["anonymous", "wrong password", "unknown user"])
def test_mosquitto_refuses_everything_else(plain_broker, users, who, case):
    credentials = {"anonymous": None,
                   "wrong password": Credentials("edge-test", users["edge-test"] + "x"),
                   "unknown user": Credentials("nobody", users["edge-test"])}[case]
    make = edge if who == "edge" else ingest
    accepted, refused = outcome(make(plain_broker.port, credentials))
    assert not accepted
    assert refused, "the broker's refusal reason should be recorded"


def test_the_edge_recovers_after_a_mosquitto_restart(plain_broker, users):
    client = edge(plain_broker.port, Credentials("edge-test", users["edge-test"]))
    try:
        assert client.start(wait_s=5)
        plain_broker.stop()
        assert wait_until(lambda: not client.connected(), 15), "the drop was not noticed"
        plain_broker.start()
        assert wait_until(client.connected, 60), "no reconnection after the restart"
        client.publish("stms/live/system/heartbeat", "{}", 0)
    finally:
        client.stop()


# ---- TLS on a real Mosquitto (D10) ------------------------------------------

def test_tls_with_the_trusted_ca_carries_a_prediction_end_to_end(tmp_path, users, pki,
                                                                 monkeypatch):
    import server.app as server
    from contracts.mqtt import CongestionClass, CongestionPrediction
    from edge.node import EdgeNode

    monkeypatch.setattr(server, "DATABASE", tmp_path / "tls.sqlite")
    broker = tls_broker(tmp_path, users, pki["good"])
    sink = ingest(broker.port, Credentials("ingest-test", users["ingest-test"]),
                  pki["trusted_ca"])
    source = edge(broker.port, Credentials("edge-test", users["edge-test"]), pki["trusted_ca"])
    try:
        assert sink.start(), "the ingest did not connect over TLS"
        assert source.start(), "the edge did not connect over TLS"
        sent = CongestionPrediction(predictions={a: CongestionClass.MEDIUM for a in "NSEW"},
                                    confidences={a: 0.55 for a in "NSEW"}, gate_value=None,
                                    model="persistence@2431c6641b9c")
        assert EdgeNode(intersection_id="tls1", transport=source).publish_prediction(sent)
        assert wait_until(lambda: sink.stored == 1, 10)
    finally:
        source.stop()
        sink.stop()
        broker.stop()


@pytest.mark.parametrize("case", ["wrong CA", "untrusted self-signed", "hostname mismatch"])
@pytest.mark.parametrize("who", ["edge", "ingest"])
def test_tls_verification_failures_do_not_connect(tmp_path, users, pki, case, who):
    cert, ca = {"wrong CA": (pki["good"], pki["wrong_ca"]),
                "untrusted self-signed": (pki["self_signed"], pki["trusted_ca"]),
                "hostname mismatch": (pki["wrong_name"], pki["trusted_ca"])}[case]
    broker = tls_broker(tmp_path, users, cert)
    try:
        make = edge if who == "edge" else ingest
        user = "edge-test" if who == "edge" else "ingest-test"
        accepted, refused = outcome(make(broker.port, Credentials(user, users[user]), ca))
        assert not accepted, f"{case}: connected although verification should fail"
        assert refused is None, "a TLS failure never reached the broker's authentication"
    finally:
        broker.stop()


def test_plain_tcp_to_the_tls_listener_does_not_connect(tmp_path, users, pki):
    broker = tls_broker(tmp_path, users, pki["good"])
    try:
        accepted, _ = outcome(edge(broker.port, Credentials("edge-test", users["edge-test"])))
        assert not accepted
    finally:
        broker.stop()


def test_no_secret_or_key_path_reaches_any_log(tmp_path, users, pki, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    broker = tls_broker(tmp_path, users, pki["good"])
    try:
        for ca in (pki["trusted_ca"], pki["wrong_ca"]):
            outcome(edge(broker.port, Credentials("edge-test", users["edge-test"]), ca))
            outcome(edge(broker.port, Credentials("edge-test", "wrong-" + users["edge-test"]), ca))
    finally:
        broker.stop()
    key_text = pki["good"][1].read_text(encoding="utf-8")
    secrets_and_paths = [*users.values(), str(pki["good"][1]), pki["good"][1].name,
                         key_text.splitlines()[1]]
    shown = caplog.text + "".join(capsys.readouterr())
    assert not [s for s in secrets_and_paths if s in shown]
    broker_log = broker.log.read_text(encoding="utf-8", errors="replace")
    assert not [p for p in users.values() if p in broker_log]
