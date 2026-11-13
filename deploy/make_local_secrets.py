"""Generate the throwaway secrets the local and CI Compose stack runs on (D15).

    python deploy/make_local_secrets.py            # writes deploy/secrets/, refuses to overwrite
    python deploy/make_local_secrets.py --force    # replaces them

**For a local or CI run only, never a deployment.**
- The CA is a fresh test CA, and its certificates expire after 2 days.
- Every password and the API token are random per run.

A deployment brings its own CA, certificates and secrets (TIM §7.4); nothing
here is one.

Everything is written under `deploy/secrets/`. That folder is gitignored and
excluded from the Docker build context (`.dockerignore`), so no secret can
reach a commit or an image layer. Nothing secret is printed.

Written:
- `ca.crt`; `broker.crt` and `broker.key`, valid for `mosquitto` and `localhost`;
- `passwd.plain`, hashed inside the broker's init container, never on the host;
- `server.env`: the API token;
- `ingest.env`: the ingest's login and CA path, as seen inside its container;
- `edge.env`: the edge user's login, for the smoke test on the host.
"""

from __future__ import annotations

import argparse
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.tls_material import make_ca, make_leaf, openssl  # noqa: E402

OUT = ROOT / "deploy" / "secrets"
FILES = ("ca.crt", "broker.crt", "broker.key", "passwd.plain", "server.env", "ingest.env", "edge.env")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--force", action="store_true", help="replace secrets that already exist")
    args = ap.parse_args(argv)
    if openssl() is None:
        print("no openssl command on PATH (Git for Windows provides one); nothing written")
        return 1
    present = [f for f in FILES if (args.out / f).exists()]
    if present and not args.force:
        print(f"{args.out} already holds {', '.join(present)}; pass --force to replace them")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        ca = make_ca(work, "ca")
        leaf = make_leaf(work, "broker", ca, "DNS:mosquitto, DNS:localhost, IP:127.0.0.1")
        shutil.copyfile(ca[0], args.out / "ca.crt")          # the CA key is discarded
        shutil.copyfile(leaf[0], args.out / "broker.crt")
        shutil.copyfile(leaf[1], args.out / "broker.key")
    ingest_pw, edge_pw = secrets.token_urlsafe(18), secrets.token_urlsafe(18)
    writes = {
        "passwd.plain": f"ingest:{ingest_pw}\nedge:{edge_pw}\n",
        "server.env": f"STMS_API_TOKEN={secrets.token_urlsafe(24)}\n",
        "ingest.env": (f"STMS_MQTT_USERNAME=ingest\nSTMS_MQTT_PASSWORD={ingest_pw}\n"
                       "STMS_MQTT_CA_FILE=/secrets/ca.crt\n"),
        "edge.env": f"STMS_MQTT_USERNAME=edge\nSTMS_MQTT_PASSWORD={edge_pw}\n",
    }
    for name, text in writes.items():
        (args.out / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(FILES)} files to {args.out} (local and CI use only; certificates expire in 2 days)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
