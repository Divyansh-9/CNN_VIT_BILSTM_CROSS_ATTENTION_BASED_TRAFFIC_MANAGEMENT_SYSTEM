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
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

__all__ = ["USERNAME_ENV", "PASSWORD_ENV", "CredentialError", "Credentials",
           "credentials_from_env"]

USERNAME_ENV = "STMS_MQTT_USERNAME"
PASSWORD_ENV = "STMS_MQTT_PASSWORD"


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
