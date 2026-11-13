"""How a client authenticates to the broker (NFR-11).

    set STMS_MQTT_USERNAME=edge-ne8th
    set STMS_MQTT_PASSWORD=...        (in the environment, never on the command line)

NFR-11 requires a broker that refuses unauthenticated connections. Both MQTT
clients, the edge's `MqttTransport` and the server's `PredictionIngest`, take
`Credentials` and send them when they connect. The credentials come from the
environment only, so they never reach shell history, a process list, a log or
a file committed to git.

- **Both or neither.** A username without a password, or a password without a
  username, is refused at start-up. Half a credential would either connect
  anonymously or fail in a way that looks like a network fault. With neither
  set the client connects anonymously, which only a development broker accepts.
- **The password is never shown.** `Credentials` leaves it out of its repr, and
  every message here names the variable, never its value.

**TLS when a CA is configured** (D10). With `STMS_MQTT_CA_FILE` naming a PEM
CA certificate, both clients connect over TLS. They trust that CA only,
require the broker's certificate, check that its name matches the host, and
refuse anything older than TLS 1.2. There is no setting that turns
verification off. A CA file that is missing, unreadable or not a certificate
is refused at start-up, never treated as "no TLS". With the variable unset,
the connection is plain TCP, and the programs say so.
"""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

__all__ = ["USERNAME_ENV", "PASSWORD_ENV", "CA_FILE_ENV", "CredentialError", "Credentials",
           "TlsConfigError", "credentials_from_env", "ca_file_from_env", "client_tls_context"]

USERNAME_ENV = "STMS_MQTT_USERNAME"
PASSWORD_ENV = "STMS_MQTT_PASSWORD"
CA_FILE_ENV = "STMS_MQTT_CA_FILE"


class CredentialError(ValueError):
    """Credentials configured halfway. The message names variables, never values."""


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str = field(repr=False)


def credentials_from_env(environ: Mapping[str, str] | None = None) -> Credentials | None:
    """Both variables set: `Credentials`. Neither: None, an anonymous connection.
    One without the other is refused. An empty variable counts as unset."""
    environ = os.environ if environ is None else environ
    username = environ.get(USERNAME_ENV, "").strip()
    password = environ.get(PASSWORD_ENV, "")
    if not username and not password:
        return None
    if not password:
        raise CredentialError(f"{USERNAME_ENV} is set but {PASSWORD_ENV} is not; "
                              f"set both, or neither for an anonymous development broker")
    if not username:
        raise CredentialError(f"{PASSWORD_ENV} is set but {USERNAME_ENV} is not; "
                              f"set both, or neither for an anonymous development broker")
    return Credentials(username, password)

class TlsConfigError(ValueError):
    """A CA file that cannot be used. The message names the variable, not the path."""


def client_tls_context(ca_file: Path) -> ssl.SSLContext:
    """Verify the broker against this CA only: certificate required, hostname
    checked, TLS 1.2 or later. Raises on a CA file that is not a certificate."""
    context = ssl.create_default_context(cafile=str(ca_file))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    assert context.verify_mode is ssl.CERT_REQUIRED and context.check_hostname
    return context


def ca_file_from_env(environ: Mapping[str, str] | None = None) -> Path | None:
    """`STMS_MQTT_CA_FILE` checked, or None for plain TCP. An unusable file is
    refused rather than silently ignored: falling back to plaintext would
    defeat the setting."""
    environ = os.environ if environ is None else environ
    value = environ.get(CA_FILE_ENV, "").strip()
    if not value:
        return None
    path = Path(value)
    try:
        client_tls_context(path)
    except (OSError, ssl.SSLError, ValueError):
        raise TlsConfigError(f"{CA_FILE_ENV} does not name a readable PEM CA certificate; "
                             f"refusing to connect without TLS") from None
    return path
