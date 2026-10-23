"""Throwaway TLS material for the tests, made with the `openssl` command (D10).

Nothing here is committed: every call writes a fresh CA, keys and
certificates into a temporary directory. `cryptography` is not a project
dependency, so the `openssl` tool is used, and the caller skips without it.

The certificates are strict enough for Python's default verification, which
since 3.13 includes `VERIFY_X509_STRICT`:
- the CA is `basicConstraints` critical, with `keyCertSign`;
- each leaf carries `authorityKeyIdentifier` and the `serverAuth` usage.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

CA_CNF = """[req]
prompt = no
distinguished_name = dn
x509_extensions = v3_ca
[dn]
CN = {cn}
[v3_ca]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
"""

LEAF_CNF = """[req]
prompt = no
distinguished_name = dn
[dn]
CN = {cn}
"""

LEAF_EXT = """basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid, issuer
subjectAltName = {san}
"""

SELF_SIGNED_EXT = """[req]
prompt = no
distinguished_name = dn
x509_extensions = leaf
[dn]
CN = {cn}
[leaf]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
subjectAltName = {san}
"""


def openssl() -> str | None:
    return shutil.which("openssl")


def _run(*args: str, cwd: Path) -> None:
    subprocess.run([openssl(), *args], cwd=cwd, check=True, capture_output=True, timeout=60)


def make_ca(directory: Path, name: str) -> tuple[Path, Path]:
    """A CA certificate and key: (cert, key)."""
    (directory / f"{name}.cnf").write_text(CA_CNF.format(cn=f"STMS test CA {name}"),
                                          encoding="utf-8")
    _run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
         "-keyout", f"{name}.key", "-out", f"{name}.crt", "-config", f"{name}.cnf",
         cwd=directory)
    return directory / f"{name}.crt", directory / f"{name}.key"


def make_leaf(directory: Path, name: str, ca: tuple[Path, Path], san: str) -> tuple[Path, Path]:
    """A server certificate signed by `ca`, for the given subjectAltName."""
    (directory / f"{name}.cnf").write_text(LEAF_CNF.format(cn=name), encoding="utf-8")
    (directory / f"{name}.ext").write_text(LEAF_EXT.format(san=san), encoding="utf-8")
    _run("req", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{name}.key",
         "-out", f"{name}.csr", "-config", f"{name}.cnf", cwd=directory)
    _run("x509", "-req", "-in", f"{name}.csr", "-CA", str(ca[0]), "-CAkey", str(ca[1]),
         "-CAcreateserial", "-days", "2", "-out", f"{name}.crt", "-extfile", f"{name}.ext",
         cwd=directory)
    return directory / f"{name}.crt", directory / f"{name}.key"


def make_self_signed(directory: Path, name: str, san: str) -> tuple[Path, Path]:
    """A server certificate that no CA vouches for."""
    (directory / f"{name}.cnf").write_text(SELF_SIGNED_EXT.format(cn=name, san=san),
                                          encoding="utf-8")
    _run("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
         "-keyout", f"{name}.key", "-out", f"{name}.crt", "-config", f"{name}.cnf",
         cwd=directory)
    return directory / f"{name}.crt", directory / f"{name}.key"
