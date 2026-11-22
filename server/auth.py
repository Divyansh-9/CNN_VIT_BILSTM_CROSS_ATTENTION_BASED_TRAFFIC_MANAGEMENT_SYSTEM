"""Accounts and sign-in sessions for the dashboard (owner's request, 2026-11-14).

Nobody reaches the dashboard's data without signing in. This module is the one
place that decides who is signed in, and it has no HTTP framework in it, so the
control server (`server/app.py`, FastAPI) and the local workbench
(`scripts/demo_launcher.py`, `http.server`) answer `/auth/*` identically through
`api()` and check a session the same way through `session_user()`.

**Passwords.** Stored only as scrypt hashes (N=2^17, r=8, p=1, a 16-byte random
salt per password; OWASP's recommended scrypt setting), in a self-describing
string so the cost can be raised later without breaking old hashes. A plain
password is never stored, logged or returned. An unknown account still costs a
full hash, so the response time does not reveal which accounts exist.

**Sessions.** A session is a random 256-bit token in an `HttpOnly`,
`SameSite=Strict` cookie. The database keeps only its SHA-256, so a copy of the
database cannot be replayed as a live session. There is no signing key to leak:
the token means nothing without the row. A session ends at whichever comes
first: sign-out, its absolute lifetime (`STMS_SESSION_HOURS`, default 12 h; with
"Remember me", `STMS_REMEMBER_DAYS`, default 30 days), or, without "Remember
me", `STMS_SESSION_IDLE_MINUTES` (default 120) without a request. A password
reset ends every session of that account.

**Guessing.** Five wrong passwords for one account within 15 minutes lock that
account's sign-in for 15 minutes; 30 failures from one client address in the
same window lock that address. The refusal says when to try again and nothing
about whether the account exists.

**Forged requests.** Every `/auth` POST must be JSON (a cross-site form cannot
send that type without a preflight) and, when the browser names an Origin, the
Origin must be the page's own host. The cookie is `SameSite=Strict` as well.

**Password resets** are single-use tokens valid for 30 minutes, stored hashed.
The link goes by e-mail when `STMS_SMTP_HOST` is configured; otherwise it is
written as an .eml file to the outbox folder (`STMS_AUTH_OUTBOX`, default
`data/server/outbox`), which only someone with access to this computer can read.
The link's address comes from `STMS_PUBLIC_URL`, never from the request's Host
header, so a forged Host cannot point a reset link at another site. The answer
to a reset request is the same whether or not the address has an account.

**Configuration**, all optional, all from the environment (never the page):
`STMS_AUTH_DB` (default `data/server/auth.sqlite`), `STMS_COOKIE_SECURE=1` (set
it whenever the page is served over HTTPS), `STMS_SESSION_HOURS`,
`STMS_REMEMBER_DAYS`, `STMS_SESSION_IDLE_MINUTES`, `STMS_PUBLIC_URL`,
`STMS_SMTP_HOST`, `STMS_SMTP_PORT`, `STMS_SMTP_USER`, `STMS_SMTP_PASSWORD`,
`STMS_SMTP_FROM`, `STMS_AUTH_OUTBOX`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import smtplib
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass, field
from email.message import EmailMessage
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

AUTH_DB_ENV = "STMS_AUTH_DB"
DEFAULT_AUTH_DB = Path("data/server/auth.sqlite")
COOKIE = "stms_session"

#: scrypt cost. Tests lower N for speed; production keeps 2**17.
SCRYPT_N = 2 ** 17
SCRYPT_R = 8
SCRYPT_P = 1
_SCRYPT_MAXMEM = 2 ** 28

MAX_ACCOUNT_FAILURES = 5
MAX_CLIENT_FAILURES = 30
LOCK_WINDOW_S = 15 * 60
RESET_VALID_S = 30 * 60
MAX_RESETS_PER_HOUR = 3
MAX_BODY = 16 * 1024
_TOUCH_EVERY_S = 60

SIGN_IN_REQUIRED = "sign in required"

NAME_RE = re.compile(r"^[^\x00-\x1f\x7f<>]{2,80}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                      r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,31}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,128}$")
#: Fragments that make a password guessable whatever else it contains.
WEAK_FRAGMENTS = ("password", "passw0rd", "qwerty", "123456", "letmein", "welcome", "admin", "iloveyou",
                  "abc123", "traffic", "stms")
PASSWORD_MIN, PASSWORD_MAX = 10, 128


# --------------------------------------------------------------------------- settings ---

def _number(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default
    return min(max(value, low), high)


def session_seconds() -> float:
    return _number("STMS_SESSION_HOURS", 12, 0.05, 24 * 7) * 3600


def remember_seconds() -> float:
    return _number("STMS_REMEMBER_DAYS", 30, 1, 90) * 86400


def idle_seconds() -> float:
    return _number("STMS_SESSION_IDLE_MINUTES", 120, 1, 24 * 60) * 60


def cookie_secure() -> bool:
    return os.environ.get("STMS_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")


def database_path() -> Path:
    return Path(os.environ.get(AUTH_DB_ENV, "").strip() or DEFAULT_AUTH_DB)


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the account store, creating it on first use. Resolved at call time."""
    path = Path(path) if path is not None else database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL,
            password_changed_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            last_seen REAL NOT NULL,
            persistent INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id);
        CREATE TABLE IF NOT EXISTS password_resets (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS login_failures (
            key TEXT NOT NULL,
            at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS login_failures_key ON login_failures (key, at);
    """)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# --------------------------------------------------------------------------- passwords ---

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                            maxmem=_SCRYPT_MAXMEM, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p),
                                maxmem=_SCRYPT_MAXMEM, dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


_dummy: dict[int, str] = {}


def _burn(password: str) -> None:
    """Spend one hash on an account that does not exist, so timing tells nothing."""
    if SCRYPT_N not in _dummy:
        _dummy[SCRYPT_N] = hash_password(secrets.token_urlsafe(12))
    verify_password(password, _dummy[SCRYPT_N])


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii", "replace")).hexdigest()


# --------------------------------------------------------------------------- validation ---

def password_problems(password: str, username: str = "", email: str = "") -> list[str]:
    """Every rule the password breaks, in words a person can act on. Empty means strong."""
    problems = []
    if len(password) < PASSWORD_MIN:
        problems.append(f"Use at least {PASSWORD_MIN} characters.")
    if len(password) > PASSWORD_MAX:
        problems.append(f"Use at most {PASSWORD_MAX} characters.")
    if not re.search(r"[a-z]", password):
        problems.append("Add a lowercase letter.")
    if not re.search(r"[A-Z]", password):
        problems.append("Add an uppercase letter.")
    if not re.search(r"[0-9]", password):
        problems.append("Add a number.")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("Add a symbol, such as ! or #.")
    lowered = password.lower()
    personal = [part for part in (username.lower(), email.lower().split("@")[0]) if len(part) >= 3]
    if any(part in lowered for part in personal):
        problems.append("Do not include your username or e-mail name.")
    if any(fragment in lowered for fragment in WEAK_FRAGMENTS):
        problems.append("Avoid common words such as 'password' or '123456'.")
    return problems


def _text(body: dict, key: str, limit: int = 320) -> str:
    value = body.get(key, "")
    return value if isinstance(value, str) and len(value) <= limit else ""


def public_user(row) -> dict:
    return {"id": row["id"], "full_name": row["full_name"], "email": row["email"], "username": row["username"]}


# --------------------------------------------------------------------------- accounts ---

def register(body: dict) -> tuple[dict | None, dict[str, str]]:
    """Create an account. Returns (user, {}) or (None, {field: message})."""
    full_name = " ".join(_text(body, "full_name", 200).split())
    email = _text(body, "email").strip().lower()
    username = _text(body, "username", 64).strip()
    password = _text(body, "password", 256)
    confirm = _text(body, "confirm_password", 256)
    errors: dict[str, str] = {}
    if not NAME_RE.match(full_name):
        errors["full_name"] = "Enter your full name (2 to 80 characters)."
    if len(email) > 254 or not EMAIL_RE.match(email):
        errors["email"] = "Enter a valid e-mail address."
    if not USERNAME_RE.match(username):
        errors["username"] = "Use 3 to 32 letters, numbers, dots, dashes or underscores, starting with a letter."
    problems = password_problems(password, username, email)
    if problems:
        errors["password"] = " ".join(problems)
    if not confirm or confirm != password:
        errors["confirm_password"] = "The passwords do not match."
    if body.get("accept_terms") is not True:
        errors["accept_terms"] = "Accept the terms and conditions to continue."
    with closing(connect()) as db:
        if "email" not in errors and db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            errors["email"] = "An account with this e-mail already exists."
        if "username" not in errors and db.execute("SELECT 1 FROM users WHERE username = ?",
                                                   (username,)).fetchone():
            errors["username"] = "This username is taken."
        if errors:
            return None, errors
        now = time.time()
        try:
            with db:
                cursor = db.execute(
                    "INSERT INTO users (full_name, email, username, password_hash, created_at, password_changed_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)", (full_name, email, username, hash_password(password), now, now))
        except sqlite3.IntegrityError:
            # Taken between the check and the insert.
            return None, {"username": "This username or e-mail was just registered. Choose another."}
        row = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    log.info("account registered (id %s)", row["id"])
    return public_user(row), {}


def _failures(db, key: str, now: float) -> list[float]:
    return [r[0] for r in db.execute("SELECT at FROM login_failures WHERE key = ? AND at > ? ORDER BY at",
                                     (key, now - LOCK_WINDOW_S))]


def _locked_for(db, keys: list[tuple[str, int]], now: float) -> int:
    """Seconds until sign-in may be tried again, or 0."""
    wait = 0
    for key, limit in keys:
        times = _failures(db, key, now)
        if len(times) >= limit:
            wait = max(wait, int(times[-limit] + LOCK_WINDOW_S - now) + 1)
    return wait


@dataclass
class SignIn:
    token: str | None = None
    user: dict | None = None
    error: str | None = None
    retry_after: int = 0
    persistent: bool = False


def sign_in(body: dict, client: str = "") -> SignIn:
    identifier = _text(body, "identifier").strip()
    password = _text(body, "password", 256)
    remember = body.get("remember") is True
    if not identifier or not password:
        return SignIn(error="Enter your e-mail or username and your password.")
    now = time.time()
    account_key = "account:" + identifier.lower()
    client_key = "client:" + (client or "unknown")
    with closing(connect()) as db:
        wait = _locked_for(db, [(account_key, MAX_ACCOUNT_FAILURES), (client_key, MAX_CLIENT_FAILURES)], now)
        if wait:
            minutes = max(1, round(wait / 60))
            return SignIn(error=f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes > 1 else ''}.",
                          retry_after=wait)
        column = "email" if "@" in identifier else "username"
        row = db.execute(f"SELECT * FROM users WHERE {column} = ?", (identifier,)).fetchone()  # noqa: S608
        if row is None:
            _burn(password)
            ok = False
        else:
            ok = verify_password(password, row["password_hash"])
        if not ok:
            with db:
                db.execute("INSERT INTO login_failures (key, at) VALUES (?, ?), (?, ?)",
                           (account_key, now, client_key, now))
                db.execute("DELETE FROM login_failures WHERE at < ?", (now - 2 * LOCK_WINDOW_S,))
            return SignIn(error="The e-mail, username or password is not correct.")
        token = secrets.token_urlsafe(32)
        lifetime = remember_seconds() if remember else session_seconds()
        with db:
            db.execute("DELETE FROM login_failures WHERE key = ?", (account_key,))
            db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            db.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen, persistent)"
                       " VALUES (?, ?, ?, ?, ?, ?)", (_token_hash(token), row["id"], now, now + lifetime, now,
                                                       int(remember)))
    log.info("signed in (account %s)", row["id"])
    return SignIn(token=token, user=public_user(row), persistent=remember)


def session_user(token: str | None) -> dict | None:
    """The signed-in user for a session token, or None. Ends a session that has expired."""
    if not token or not TOKEN_RE.match(token):
        return None
    now = time.time()
    with closing(connect()) as db:
        row = db.execute("SELECT s.token_hash, s.expires_at, s.last_seen, s.persistent, u.* FROM sessions s "
                         "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (_token_hash(token),)).fetchone()
        if row is None:
            return None
        idle_out = not row["persistent"] and now - row["last_seen"] > idle_seconds()
        if row["expires_at"] <= now or idle_out:
            with db:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (row["token_hash"],))
            return None
        if now - row["last_seen"] > _TOUCH_EVERY_S:
            with db:
                db.execute("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", (now, row["token_hash"]))
        user = public_user(row)
        expires = row["expires_at"] if row["persistent"] else min(row["expires_at"], now + idle_seconds())
        user["session"] = {"expires_at": expires, "persistent": bool(row["persistent"])}
        return user


def sign_out(token: str | None) -> None:
    if token and TOKEN_RE.match(token):
        with closing(connect()) as db, db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))


# --------------------------------------------------------------------------- resets ---

def public_url() -> str:
    return (os.environ.get("STMS_PUBLIC_URL", "").strip() or "http://127.0.0.1:8000").rstrip("/")


def deliver(to: str, subject: str, text: str) -> str:
    """Send by SMTP when configured, else write an .eml to the outbox. Returns how."""
    message = EmailMessage()
    message["From"] = os.environ.get("STMS_SMTP_FROM", "").strip() or "STMS <no-reply@localhost>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    host = os.environ.get("STMS_SMTP_HOST", "").strip()
    if host:
        port = int(_number("STMS_SMTP_PORT", 587, 1, 65535))
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            user = os.environ.get("STMS_SMTP_USER", "").strip()
            if user:
                smtp.login(user, os.environ.get("STMS_SMTP_PASSWORD", ""))
            smtp.send_message(message)
        return "smtp"
    outbox = Path(os.environ.get("STMS_AUTH_OUTBOX", "").strip() or "data/server/outbox")
    outbox.mkdir(parents=True, exist_ok=True)
    name = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4) + ".eml"
    (outbox / name).write_bytes(bytes(message))
    log.warning("no SMTP server configured: a password-reset message was written to %s", outbox)
    return "outbox"


def request_reset(body: dict, link_base: str | None = None) -> None:
    """Start a reset if the address has an account. Says nothing either way."""
    email = _text(body, "email").strip().lower()
    if not EMAIL_RE.match(email):
        return
    now = time.time()
    with closing(connect()) as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            _burn(email)
            return
        recent = db.execute("SELECT COUNT(*) FROM password_resets WHERE user_id = ? AND created_at > ?",
                            (row["id"], now - 3600)).fetchone()[0]
        if recent >= MAX_RESETS_PER_HOUR:
            return
        token = secrets.token_urlsafe(32)
        with db:
            db.execute("INSERT INTO password_resets (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                       (_token_hash(token), row["id"], now, now + RESET_VALID_S))
    link = f"{(link_base or public_url()).rstrip('/')}/dashboard/#reset/{token}"
    text = (f"Hello {row['full_name']},\n\nSomeone asked to reset the password of your STMS account "
            f"({row['username']}). To choose a new password, open this link within 30 minutes:\n\n{link}\n\n"
            "If it was not you, ignore this message: your password stays as it is.\n")
    try:
        deliver(row["email"], "Reset your STMS password", text)
    except (OSError, smtplib.SMTPException) as error:
        log.error("could not send the password-reset message: %s", type(error).__name__)


def reset_password(body: dict) -> dict[str, str]:
    """Set a new password from a reset token. Returns {field: message}; empty means done."""
    token = _text(body, "token", 200).strip()
    password = _text(body, "password", 256)
    confirm = _text(body, "confirm_password", 256)
    if not TOKEN_RE.match(token):
        return {"token": "This reset link is not valid. Ask for a new one."}
    now = time.time()
    with closing(connect()) as db:
        row = db.execute("SELECT r.token_hash, r.expires_at, r.used, u.* FROM password_resets r "
                         "JOIN users u ON u.id = r.user_id WHERE r.token_hash = ?", (_token_hash(token),)).fetchone()
        if row is None or row["used"] or row["expires_at"] <= now:
            return {"token": "This reset link has expired or was already used. Ask for a new one."}
        errors = {}
        problems = password_problems(password, row["username"], row["email"])
        if problems:
            errors["password"] = " ".join(problems)
        if not confirm or confirm != password:
            errors["confirm_password"] = "The passwords do not match."
        if errors:
            return errors
        with db:
            db.execute("UPDATE users SET password_hash = ?, password_changed_at = ? WHERE id = ?",
                       (hash_password(password), now, row["id"]))
            db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ?", (row["id"],))
            db.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
            db.execute("DELETE FROM login_failures WHERE key IN (?, ?)",
                       ("account:" + row["email"].lower(), "account:" + row["username"].lower()))
    log.info("password reset (account %s); every session ended", row["id"])
    return {}


# --------------------------------------------------------------------------- HTTP glue ---

def same_origin(origin: str | None, host: str | None) -> bool:
    """A browser's Origin, when it sends one, must name the host the page came from."""
    if origin is None:
        return True
    try:
        return bool(host) and urlsplit(origin).netloc.lower() == host.lower()
    except ValueError:
        return False


def cookie_token(header: str | None) -> str | None:
    if not header:
        return None
    try:
        jar = SimpleCookie()
        jar.load(header)
    except CookieError:
        return None
    morsel = jar.get(COOKIE)
    return morsel.value if morsel else None


def cookie_header(token: str | None, max_age: int | None = None) -> str:
    """Set-Cookie for a new session (token) or for signing out (None)."""
    parts = [f"{COOKIE}={token or ''}", "Path=/", "HttpOnly", "SameSite=Strict"]
    if cookie_secure():
        parts.append("Secure")
    if token is None:
        parts.append("Max-Age=0")
    elif max_age is not None:
        parts.append(f"Max-Age={int(max_age)}")
    return "; ".join(parts)


@dataclass
class Reply:
    status: int
    payload: dict
    set_cookie: str | None = None
    headers: dict = field(default_factory=dict)


def api(method: str, action: str, *, raw: bytes = b"", content_type: str | None = None,
        origin: str | None = None, host: str | None = None, token: str | None = None,
        client: str = "", link_base: str | None = None) -> Reply:
    """Answer one `/auth/<action>` request. Both servers call this and nothing else."""
    if method == "GET":
        if action != "me":
            return Reply(404, {"detail": "not found"})
        user = session_user(token)
        return Reply(200, {"user": user}) if user else Reply(401, {"detail": SIGN_IN_REQUIRED})
    if method != "POST" or action not in ("register", "login", "logout", "forgot", "reset"):
        return Reply(404, {"detail": "not found"})
    if not same_origin(origin, host):
        return Reply(403, {"detail": "this request did not come from this site"})
    if (content_type or "").split(";")[0].strip().lower() != "application/json":
        return Reply(415, {"detail": "send JSON"})
    if len(raw) > MAX_BODY:
        return Reply(413, {"detail": "too large"})
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return Reply(400, {"detail": "not JSON"})
    if not isinstance(body, dict):
        return Reply(400, {"detail": "send a JSON object"})

    if action == "register":
        user, errors = register(body)
        if errors:
            return Reply(422, {"detail": "Check the highlighted fields.", "errors": errors})
        return Reply(201, {"user": user, "message": "Account created. Sign in to continue."})
    if action == "login":
        result = sign_in(body, client)
        if result.error:
            status = 429 if result.retry_after else 401
            headers = {"Retry-After": str(result.retry_after)} if result.retry_after else {}
            return Reply(status, {"detail": result.error}, headers=headers)
        max_age = int(remember_seconds()) if result.persistent else None
        return Reply(200, {"user": result.user}, set_cookie=cookie_header(result.token, max_age))
    if action == "logout":
        sign_out(token)
        return Reply(200, {"signed_out": True}, set_cookie=cookie_header(None))
    if action == "forgot":
        request_reset(body, link_base)
        return Reply(202, {"message": "If an account uses that address, a reset link is on its way. "
                                      "It works for 30 minutes."})
    errors = reset_password(body)
    if errors:
        return Reply(422, {"detail": "The password was not changed.", "errors": errors})
    return Reply(200, {"message": "Password changed. Sign in with your new password."})
