"""The prediction and control server (S41, PRD §17, ADR-008).

    uvicorn server.app:app --port 8000

Importing this module attaches a filter to uvicorn's access log that writes a
request's path only when every segment is a short plain token, and never its
query string (P142): the default log line holds the raw path, so it recorded
every refused intersection id at full length.

**Thin on purpose.** Every rule that matters lives in `server/safety.py`, which
has no HTTP in it and is tested without starting anything. This module routes,
validates and stores. If a decision here looks surprising, the answer is in
`SignalGuard`, and the `reason` string on every response says which rule fired.

ADR-008 replaced PostgreSQL + TimescaleDB with **SQLite**: identical query
surface at this data volume, one fewer service, and the analysis notebooks read
the same file the dashboard does — which incidentally strengthens the NFR-09
reproducibility story rather than weakening it.

**NFR-13 is structural here, not a rule to remember.** No endpoint accepts an
image, no column stores one, and the request models have no field that could
carry one. Raw frames never leave the edge device; counts and predictions do.

**FR-A06's clock is the server's, not the edge's.** The edge reports when it
last spoke; the server decides whether that is too long ago. A device that has
crashed cannot report that it has crashed, so a timeout measured on the sender
would never fire in the case it exists for.

**Writes need a bearer token; reads do not** (NFR-12 as amended, ADR-008, D9).
Every POST requires `Authorization: Bearer <token>`, matched in constant time
against `STMS_API_TOKEN` in the server's environment. With that variable unset
or empty, every POST is refused: there is no switch that turns the check off.
GET endpoints, and the dashboard that uses them, stay open for reading, so
stored observations and forecasts are visible to anyone who can reach the
server. The token crosses plain HTTP, which is why the server stays on
127.0.0.1. Neither the token nor a refused value is ever logged or echoed.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import sqlite3
import time
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, Field

from contracts.mqtt import (INTERSECTION_ID, ContractError, Topic, check_intersection_id, check_lane,
                            decode)

from server.safety import Decision, SafetyLimits, SignalGuard

DATABASE = Path("data/server/stms.sqlite")
#: The bearer token every POST must carry (D9). Read from the environment only.
API_TOKEN_ENV = "STMS_API_TOKEN"
#: The one refusal, whatever was wrong: missing, malformed or wrong. It never
#: says which, and never repeats what was sent.
WRITE_REFUSED = "a valid bearer token is required to write"

log = logging.getLogger(__name__)
APPROACHES = ("N", "S", "E", "W")
Approach = Literal["N", "S", "E", "W"]
#: The most vehicles, or queued vehicles, one approach can report in one
#: observation. Far above any real junction; a larger value is a fault, and an
#: unbounded int was a stored, `/history`-returned channel of 8 bytes a field (P142).
MAX_OBSERVED = 10_000
#: The oldest heartbeat age, or forecast age, a sender may report: about 11.6
#: days. Beyond that the edge is long gone either way, and an unbounded float
#: was formatted at full length into the stored `reason` (P142).
MAX_AGE_S = 1_000_000.0

def require_write_token(authorization: str | None = Header(default=None)) -> None:
    """Refuse a write without the configured bearer token (D9). Fails closed:
    with no token configured, no write is accepted."""
    expected = os.environ.get(API_TOKEN_ENV, "").strip()
    scheme, _, supplied = (authorization or "").partition(" ")
    supplied = supplied.strip()
    if (not expected or scheme.lower() != "bearer" or not supplied
            or not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))):
        raise HTTPException(401, WRITE_REFUSED, headers={"WWW-Authenticate": "Bearer"})


WRITE = [Depends(require_write_token)]


def write_auth_header() -> dict[str, str]:
    """What an HTTP client sends to write (D9): the token from its environment."""
    return {"Authorization": f"Bearer {os.environ.get(API_TOKEN_ENV, '').strip()}"}


@asynccontextmanager
async def lifespan(_app):
    if not os.environ.get(API_TOKEN_ENV, "").strip():
        log.warning("%s is not set; every POST will be refused until it is (D9)",
                    API_TOKEN_ENV)
    yield


app = FastAPI(
    title="STMS control server",
    summary="Counts in, signal commands out. No frames, ever (NFR-13).",
    # P142: Starlette's default answers `/history/<id>/` with a 307 whose
    # Location header repeats the path, the query string and the Host header,
    # before any route — and so before any id check — runs.
    redirect_slashes=False,
    lifespan=lifespan,
)

_LOGGABLE_SEGMENT = re.compile(r"[A-Za-z0-9_.-]{0,32}")


def loggable_path(full_path: str) -> str:
    """What the access log may say about a request target (P142). Never the
    query string; the path only when every sender-chosen part of it is
    already known to be safe. uvicorn's line held the raw target, so every
    refused id was logged verbatim, at any length.

    - A path that is not short plain tokens: `<refused path>`.
    - An API route: logged only if each of its path parameters is an
      `intersection_id` that passes the contract's rule. Matching the route is
      not enough: `/history/<id>.x` matches `/history/{intersection_id}` and is
      then refused by the handler, after uvicorn has logged it.
    - A static mount: `<mount>/<static>`. A mount matches any sub-path, so
      its sub-path is sender-chosen text and is never logged.
    - Nothing matched: `<unmatched path>`.
    """
    # Through FastAPI, which is pinned: starlette is only a transitive
    # dependency, and test_requirements_complete requires direct imports pinned.
    from fastapi.routing import Mount

    path, _, query = full_path.partition("?")
    suffix = "?<query>" if query else ""
    if len(path) > 256 or not all(_LOGGABLE_SEGMENT.fullmatch(s) for s in path.split("/")):
        return "<refused path>"
    for route in app.routes:
        regex = getattr(route, "path_regex", None)
        match = regex.match(path) if regex is not None else None
        if match is None:
            continue
        if isinstance(route, Mount):
            return f"{route.path}/<static>{suffix}"
        if all(name == "intersection_id" and INTERSECTION_ID.fullmatch(value)
               for name, value in match.groupdict().items()):
            return path + suffix
        return "<refused path>"
    return "<unmatched path>"


class AccessLogFilter(logging.Filter):
    """Rewrites the target in uvicorn's access record, whose args are
    (client, method, target, http_version, status)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, target, version, status = record.args
            record.args = (client, method, loggable_path(str(target)), version, status)
        return True


logging.getLogger("uvicorn.access").addFilter(AccessLogFilter())


@app.exception_handler(RequestValidationError)
async def refuse_without_echo(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's own 422 quotes the submitted value (`input`) and can name a
    submitted key in `loc`, which turns a refusal into an echo channel (P142).
    This keeps what a sender needs — where, what kind of error, why — and drops
    the rest: `input` and `ctx` always, and `loc` below the field name, where a
    dictionary key the sender chose would appear."""
    detail = [{"type": error.get("type"), "loc": list(error.get("loc", ()))[:2],
               "msg": error.get("msg")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


def valid_id(intersection_id: str) -> str:
    """The path's intersection id, or a 422 that does not quote it (P142)."""
    try:
        return check_intersection_id(intersection_id)
    except ContractError as error:
        raise HTTPException(422, str(error)) from error


Count = Annotated[int, Field(ge=0, le=MAX_OBSERVED)]


def _upper(value):
    return value.upper() if isinstance(value, str) else value


class Counts(BaseModel):
    """One observation from one intersection.

    Deliberately has no image field, and no field that could hold one. NFR-13
    is enforced by the shape of this model rather than by a check somewhere
    that could be forgotten.
    """

    # P142: every field is closed or bounded. The id is the contract's pattern;
    # every key and the emergency approach are approaches; counts are 0 to
    # MAX_OBSERVED; ages are finite, non-negative and capped. Before, the
    # emergency approach was free text that reached the stored `reason`, counts
    # were any 64-bit integer, and a NaN heartbeat age compared false against
    # the timeout and so skipped the FR-A06 fallback.
    intersection_id: str = Field(pattern=f"^{INTERSECTION_ID.pattern}$")
    counts: dict[Approach, Count]
    queues: dict[Approach, Count] = Field(default_factory=dict)
    # Lower case is accepted and normalised, as `SignalGuard` always has (`.upper()`).
    emergency_approach: Annotated[Approach | None, BeforeValidator(_upper)] = None
    seconds_since_heartbeat: float = Field(0.0, ge=0.0, le=MAX_AGE_S, allow_inf_nan=False)
    # Accepted and unused by the server today; closed so that it is not an
    # unbounded inbound field either.
    forecast: dict[Approach, Literal["LOW", "MEDIUM", "HIGH"]] | None = None
    forecast_age_s: float | None = Field(None, ge=0.0, le=MAX_AGE_S, allow_inf_nan=False)


class CommandOut(BaseModel):
    intersection_id: str
    phase: str
    green_s: int
    all_red_s: int
    source: str
    reason: str
    clamped: bool


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the store, resolving the default **at call time**.

    `def connect(path=DATABASE)` binds the default when the module is imported,
    so reassigning `DATABASE` afterwards has no effect — the tests pointed it at
    a temporary file, every call ignored them, and three tests shared one real
    database. The failure looked like a query bug (nine rows where three were
    expected) and was a scoping bug.
    """
    path = Path(path) if path is not None else DATABASE
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            at REAL NOT NULL,
            intersection_id TEXT NOT NULL,
            count_n INTEGER, count_s INTEGER, count_e INTEGER, count_w INTEGER,
            queue_n INTEGER, queue_s INTEGER, queue_e INTEGER, queue_w INTEGER,
            phase TEXT NOT NULL,
            green_s INTEGER NOT NULL,
            source TEXT NOT NULL,
            reason TEXT NOT NULL,
            clamped INTEGER NOT NULL
        )""")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS observations_at "
        "ON observations (intersection_id, at)")
    # ADR-026: predictions arrive from the edge, where MFSTNet runs. Stored as
    # the contract's own encoding plus the model id, so what the dashboard
    # shows can be traced to the verified graph that produced it.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            at REAL NOT NULL,
            intersection_id TEXT NOT NULL,
            model TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
    # ADR-027: the next-minute count is a different output from the class, so
    # it is a different table. It cannot be read back as a class by accident.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS count_forecasts (
            at REAL NOT NULL,
            intersection_id TEXT NOT NULL,
            model TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
    # D21: what each lane's region held, as counted at the edge (a measurement,
    # not a forecast), so a history of observed counts exists at all (FR-UI03).
    # Per lane, as the contract publishes it: which approach a lane feeds is
    # known only at the edge.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_counts (
            at REAL NOT NULL,
            intersection_id TEXT NOT NULL,
            lane TEXT NOT NULL,
            count INTEGER NOT NULL,
            fps REAL NOT NULL
        )""")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS vehicle_counts_at "
        "ON vehicle_counts (intersection_id, at)")
    # D26: forecast checks (ADR-014 §2), kept apart from the forecasts so that
    # neither history depends on the other, and bounded by age on their own.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS forecast_checks (
            at REAL NOT NULL,
            intersection_id TEXT NOT NULL,
            session TEXT NOT NULL,
            made_ts REAL NOT NULL,
            payload TEXT NOT NULL
        )""")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS forecast_checks_at "
        "ON forecast_checks (intersection_id, at)")
    # D22: the edge's latest heartbeat, one row per intersection. It says what
    # the edge counts from and which approach each lane feeds; only the latest
    # is ever asked for, so nothing accumulates.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            intersection_id TEXT PRIMARY KEY,
            at REAL NOT NULL,
            payload TEXT NOT NULL
        )""")
    connection.commit()
    return connection


guards: dict[str, SignalGuard] = {}


def guard_for(intersection_id: str) -> SignalGuard:
    """One guard per intersection. State is per-junction, not per-process."""
    if intersection_id not in guards:
        guards[intersection_id] = SignalGuard(limits=SafetyLimits())
    return guards[intersection_id]


def propose(observation: Counts) -> tuple[str, float]:
    """What the policy wants, before any rule is applied.

    A placeholder until the trained policy is wired in: switch toward whichever
    axis is busier. It is deliberately simple and deliberately *not* silent
    about being a placeholder — `source` on the response reads `policy` either
    way, so the endpoint that reports which policy is running matters.
    """
    ns = sum(observation.counts.get(a, 0) for a in ("N", "S"))
    ew = sum(observation.counts.get(a, 0) for a in ("E", "W"))
    return ("NS" if ns >= ew else "EW"), 30.0


def record(connection: sqlite3.Connection, observation: Counts,
           decision: Decision) -> None:
    connection.execute(
        "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (time.time(), observation.intersection_id,
         *[observation.counts.get(a, 0) for a in APPROACHES],
         *[observation.queues.get(a, 0) for a in APPROACHES],
         decision.phase, decision.green_s, decision.source, decision.reason,
         int(decision.clamped)))
    connection.commit()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "limits": SafetyLimits().__dict__}


@app.post("/observation", response_model=CommandOut, dependencies=WRITE)
def observation(payload: Counts) -> CommandOut:
    """Counts in, one signal command out, with the rule that produced it."""
    # `Counts` now types every key as an approach, so pydantic refuses an
    # unknown one first. Kept as a second line, and it no longer quotes the key.
    unknown = set(payload.counts) - set(APPROACHES)
    if unknown:
        raise HTTPException(422, f"count keys must be approaches {list(APPROACHES)}")

    guard = guard_for(payload.intersection_id)
    phase, green = propose(payload)
    decision = guard.decide(
        proposed_phase=phase,
        proposed_green_s=green,
        emergency_approach=payload.emergency_approach,
        seconds_since_heartbeat=payload.seconds_since_heartbeat,
    )
    guard.apply(decision)

    with closing(connect()) as connection:
        record(connection, payload, decision)

    return CommandOut(intersection_id=payload.intersection_id,
                      phase=decision.phase, green_s=decision.green_s,
                      all_red_s=decision.all_red_s, source=decision.source,
                      reason=decision.reason, clamped=decision.clamped)


def missing_approaches(payload) -> list[str]:
    """Approaches the camera does not predict (P97a).

    Since P109 (Option A) an absent approach is `null` in `state_11_14`, never
    0.0, which is also LOW. This list states the same absence by name.
    """
    return sorted(set(APPROACHES) - set(payload.predictions))


def role_of(model: str) -> str:
    """ADR-027: which output a model id belongs to, so no response leaves a
    consumer to guess whether a number is a class or a count."""
    if model.startswith("ridge@"):
        return "next_minute_count (ridge)"
    if model.startswith("persistence@"):
        return "congestion_class (persistence)"
    return "congestion_class (MFSTNet)"


def freshness(received_at: float, horizon_sec: int, now: float | None = None) -> dict:
    """Age by the server's own clock, since edge clocks drift. A forecast older
    than its own horizon is stale: it is about a minute that has already
    passed, and it is labelled so rather than served as current."""
    age = (time.time() if now is None else now) - received_at
    return {"age_s": round(age, 1), "stale": age > horizon_sec}


def store_prediction(intersection_id: str, raw: str | bytes):
    """Validate one encoded `CongestionPrediction` and store it (ADR-026).

    The single entry point for predictions, used by the HTTP endpoint and by
    the MQTT subscriber (`server/mqtt_ingest.py`) alike, so the two paths
    cannot validate differently. Decoding through `contracts.mqtt.decode`
    checks the schema version, every field and the NFR-13 size cap before
    anything is written. Raises `ContractError` on a payload it refuses, and
    on an intersection id outside the contract's pattern (P142).
    """
    check_intersection_id(intersection_id)
    payload = decode(Topic.PREDICTION, raw)
    with closing(connect()) as connection:
        connection.execute("INSERT INTO predictions VALUES (?,?,?,?)",
                           (time.time(), intersection_id, payload.model,
                            payload.encode()))
        connection.commit()
    return payload


@app.post("/prediction/{intersection_id}", dependencies=WRITE)
def prediction(intersection_id: str, raw: str = Body(..., media_type="text/plain")) -> dict:
    """One `CongestionPrediction`, exactly as the edge encoded it — the HTTP
    stand-in for the MQTT topic of the same name, with the same validation."""
    try:
        payload = store_prediction(intersection_id, raw)
    except ContractError as error:
        raise HTTPException(422, str(error)) from error
    return {"intersection_id": intersection_id, "model": payload.model,
            "predictions": {k: v.value for k, v in payload.predictions.items()},
            "state_11_14": payload.to_state_values_or_none(),
            "missing_approaches": missing_approaches(payload)}


@app.get("/prediction/{intersection_id}/latest")
def latest_prediction(intersection_id: str) -> dict:
    valid_id(intersection_id)
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT at, model, payload FROM predictions WHERE intersection_id = ? "
            "ORDER BY at DESC LIMIT 1", (intersection_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "no prediction for this intersection yet")
    payload = decode(Topic.PREDICTION, row[2])
    return {"at": row[0], "model": row[1], "role": role_of(row[1]),
            **freshness(row[0], payload.horizon_sec),
            "predictions": {k: v.value for k, v in payload.predictions.items()},
            "confidences": dict(payload.confidences),
            "gate_value": payload.gate_value,
            "state_11_14": payload.to_state_values_or_none(),
            "missing_approaches": missing_approaches(payload)}


def store_count_forecast(intersection_id: str, raw: str | bytes):
    """Validate one encoded `CountForecast` and store it (ADR-027). The single
    entry point for count forecasts, over HTTP and over MQTT alike. The id is
    checked here for the same reason as in `store_prediction` (P142)."""
    check_intersection_id(intersection_id)
    payload = decode(Topic.COUNT_FORECAST, raw)
    with closing(connect()) as connection:
        connection.execute("INSERT INTO count_forecasts VALUES (?,?,?,?)",
                           (time.time(), intersection_id, payload.model,
                            payload.encode()))
        connection.commit()
    return payload


COUNT_NOTE = ("point estimate of each approach's mean vehicle count over the next "
              "60 s (P105); not a congestion class, and not used for signal timing")


@app.post("/count_forecast/{intersection_id}", dependencies=WRITE)
def count_forecast(intersection_id: str, raw: str = Body(..., media_type="text/plain")) -> dict:
    try:
        payload = store_count_forecast(intersection_id, raw)
    except ContractError as error:
        raise HTTPException(422, str(error)) from error
    return {"intersection_id": intersection_id, "model": payload.model,
            "role": role_of(payload.model), "counts": dict(payload.counts),
            "missing_approaches": sorted(set(APPROACHES) - set(payload.counts))}


@app.get("/count_forecast/{intersection_id}/latest")
def latest_count_forecast(intersection_id: str) -> dict:
    valid_id(intersection_id)
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT at, model, payload FROM count_forecasts WHERE intersection_id = ? "
            "ORDER BY at DESC LIMIT 1", (intersection_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "no count forecast for this intersection yet")
    payload = decode(Topic.COUNT_FORECAST, row[2])
    return {"at": row[0], "model": row[1], "role": role_of(row[1]),
            **freshness(row[0], payload.horizon_sec),
            "horizon_sec": payload.horizon_sec, "counts": dict(payload.counts),
            # Absent, never zero: zero vehicles is a forecast, absence is not.
            "missing_approaches": sorted(set(APPROACHES) - set(payload.counts)),
            "note": COUNT_NOTE}


#: The most rows a forecast-history request returns. Above it the limit is
#: clamped, not refused, as `/history` does (P142).
HISTORY_MAX = 500


def _recent(table: str, intersection_id: str, limit: int) -> list[tuple]:
    with closing(connect()) as connection:
        return connection.execute(
            f"SELECT at, model, payload FROM {table} WHERE intersection_id = ? "
            "ORDER BY at DESC LIMIT ?", (intersection_id, min(limit, HISTORY_MAX))).fetchall()


@app.get("/prediction/{intersection_id}/history")
def prediction_history(intersection_id: str, limit: int = Query(30, ge=1)) -> dict:
    """The class forecasts this server recorded, newest first (S42).

    What was published, not whether it was right: no accuracy is computed
    here, because a live score against the detector's own counts would be
    circular (ADR-014). An approach without a forecast is listed as missing,
    never filled in."""
    valid_id(intersection_id)
    rows = []
    for at, model, raw in _recent("predictions", intersection_id, limit):
        payload = decode(Topic.PREDICTION, raw)
        rows.append({"at": at, "model": model, "role": role_of(model),
                     "predictions": {k: v.value for k, v in payload.predictions.items()},
                     "missing_approaches": missing_approaches(payload)})
    return {"intersection_id": intersection_id, "rows": rows}


@app.get("/count_forecast/{intersection_id}/history")
def count_forecast_history(intersection_id: str, limit: int = Query(30, ge=1)) -> dict:
    """The count forecasts this server recorded, newest first (S42, ADR-027).
    A point estimate per approach; absent stays absent, never zero."""
    valid_id(intersection_id)
    rows = []
    for at, model, raw in _recent("count_forecasts", intersection_id, limit):
        payload = decode(Topic.COUNT_FORECAST, raw)
        rows.append({"at": at, "model": model, "role": role_of(model),
                     "counts": dict(payload.counts),
                     "missing_approaches": sorted(set(APPROACHES) - set(payload.counts))})
    return {"intersection_id": intersection_id, "rows": rows}


def store_vehicle_count(intersection_id: str, lane: str, raw: str | bytes):
    """Validate one encoded `VehicleCount` and store it (D21). The single entry
    point for observed counts, over HTTP and over MQTT alike. The id and the
    lane both travel in the topic, outside the payload, so both are checked
    here before anything is written (P142)."""
    check_intersection_id(intersection_id)
    check_lane(lane)
    payload = decode(Topic.VEHICLE_COUNT, raw)
    now = time.time()
    with closing(connect()) as connection:
        connection.execute("INSERT INTO vehicle_counts VALUES (?,?,?,?,?)",
                           (now, intersection_id, lane, payload.count, payload.fps))
        connection.commit()
    maybe_prune_vehicle_counts(now)
    return payload


#: D24: raw observed counts are operational data, kept twice the longest
#: FR-UI03 window (24 h). Graded evidence lives in committed CSVs, never here,
#: and nothing outside this module reads the table.
COUNT_RETENTION_S = 48 * 3600
PRUNE_EVERY_S = 3600
#: After a failure (a locked database, say) the next write tries again this
#: soon, not an hour later.
PRUNE_RETRY_S = 60
_next_prune = 0.0


def prune_vehicle_counts(now: float) -> int:
    """Delete counts older than the retention window; returns how many. A row
    exactly at the cutoff is kept. Safe to repeat. A full scan, measured at
    28 ms over 49 h of four lanes, so the `(intersection_id, at)` index is
    left as the history query needs it."""
    with closing(connect()) as connection:
        deleted = connection.execute("DELETE FROM vehicle_counts WHERE at < ?",
                                     (now - COUNT_RETENTION_S,)).rowcount
        connection.commit()
    return deleted


def maybe_prune_vehicle_counts(now: float) -> None:
    """Prune at most hourly, driven by writes rather than a scheduler (D24).

    The API and the MQTT ingest are separate processes on one SQLite file, so
    a scheduler thread in either would need its own start, stop and duplicate
    handling. Driven by writes, each process prunes after its own stores, the
    first one after a start included; two prunes at once are harmless, since
    the delete is idempotent. With no writes nothing grows. A failure is
    logged, never raised: the count it follows was already stored."""
    global _next_prune
    if now < _next_prune:
        return
    try:
        deleted = prune_vehicle_counts(now)
    except sqlite3.Error as error:
        _next_prune = now + PRUNE_RETRY_S
        log.warning("vehicle_counts: prune failed (%s); retrying after %d s",
                    type(error).__name__, PRUNE_RETRY_S)
        return
    _next_prune = now + PRUNE_EVERY_S
    log.info("vehicle_counts: pruned %d row(s) older than %d h", deleted,
             COUNT_RETENTION_S // 3600)


@app.post("/vehicle_count/{intersection_id}/{lane}", dependencies=WRITE)
def vehicle_count(intersection_id: str, lane: str,
                  raw: str = Body(..., media_type="text/plain")) -> dict:
    """One lane's `VehicleCount`, exactly as the edge encoded it: the HTTP
    stand-in for the per-lane MQTT topic, with the same validation."""
    try:
        payload = store_vehicle_count(intersection_id, lane, raw)
    except ContractError as error:
        raise HTTPException(422, str(error)) from error
    return {"intersection_id": intersection_id, "lane": lane, "count": payload.count}


#: FR-UI03's three views, each served as a fixed number of buckets so that a
#: day is under a hundred points per lane, never tens of thousands of rows.
COUNT_WINDOWS = {"1h": (3600, 60), "6h": (21600, 300), "24h": (86400, 900)}

VEHICLE_COUNT_NOTE = ("observed: the mean number of vehicles in each lane's counting region "
                      "per bucket, as counted at the edge; a measurement, not a forecast. "
                      "A bucket with no samples is a gap, never zero")


def count_buckets(intersection_id: str, window: str, now: float) -> dict:
    """Observed counts over one FR-UI03 window, aggregated by the server (D21).

    Buckets are aligned to multiples of their own length, so the same bucket
    keeps the same edges from one request to the next. Every bucket in the
    window is listed, oldest first; a lane with no samples in a bucket is
    absent from it, so a gap stays a gap and is never drawn as zero."""
    span, size = COUNT_WINDOWS[window]
    end = (int(now) // size + 1) * size
    start = end - span
    with closing(connect()) as connection:
        rows = connection.execute(
            "SELECT lane, CAST(at / ? AS INTEGER), AVG(count), COUNT(*) FROM vehicle_counts "
            "WHERE intersection_id = ? AND at >= ? AND at < ? GROUP BY lane, 2",
            (size, intersection_id, start, end)).fetchall()
    first = start // size
    buckets = [{"t": start + i * size, "lanes": {}} for i in range(span // size)]
    for lane, index, mean, n in rows:
        buckets[index - first]["lanes"][lane] = {"mean": round(mean, 2), "n": n}
    return {"intersection_id": intersection_id, "window": window, "bucket_s": size,
            "start": start, "end": end, "lanes": sorted({r[0] for r in rows}),
            "buckets": buckets, "note": VEHICLE_COUNT_NOTE}


@app.get("/vehicle_count/{intersection_id}/history")
def vehicle_count_history(intersection_id: str,
                          window: str = Query("1h", pattern="^(1h|6h|24h)$")) -> dict:
    """FR-UI03: observed counts over the last 1, 6 or 24 hours, per lane, in
    1, 5 or 15 minute buckets (D21). Read-only, like every GET here."""
    valid_id(intersection_id)
    return count_buckets(intersection_id, window, time.time())


def store_heartbeat(intersection_id: str, raw: str | bytes):
    """Validate one encoded `Heartbeat` and keep it as the latest (D22). The
    single entry point over HTTP and over MQTT alike.

    Within one edge session an older `ts` never replaces a newer one, so a
    late QoS 0 message cannot roll a replay's position back. A different
    session always replaces the stored one: a restart or a source switch must
    not leave the last run's clip showing, whatever either clock says.
    Returns the payload, or None when it was older and so not kept."""
    check_intersection_id(intersection_id)
    payload = decode(Topic.HEARTBEAT, raw)
    with closing(connect()) as connection:
        row = connection.execute("SELECT payload FROM heartbeats WHERE intersection_id = ?",
                                 (intersection_id,)).fetchone()
        if row is not None:
            stored = decode(Topic.HEARTBEAT, row[0])
            same = (stored.source and payload.source
                    and stored.source["session"] == payload.source["session"])
            if same and payload.ts < stored.ts:
                return None
        connection.execute("INSERT OR REPLACE INTO heartbeats VALUES (?,?,?)",
                           (intersection_id, time.time(), payload.encode()))
        connection.commit()
    return payload


@app.post("/heartbeat/{intersection_id}", dependencies=WRITE)
def heartbeat(intersection_id: str, raw: str = Body(..., media_type="text/plain")) -> dict:
    """One `Heartbeat`, exactly as the edge encoded it: the HTTP stand-in for
    the MQTT topic, with the same validation."""
    try:
        payload = store_heartbeat(intersection_id, raw)
    except ContractError as error:
        raise HTTPException(422, str(error)) from error
    return {"intersection_id": intersection_id, "kept": payload is not None}


#: The edge sends a heartbeat every 2 s step. One older than the FR-A06 link
#: timeout describes an edge that may have stopped, so it is stale, and so is
#: the source it names.
HEARTBEAT_NOTE = ("what the edge last reported about itself: its source and its lane map. "
                  "Times on this page are when the server received each message, not when "
                  "the footage was recorded")


@app.get("/heartbeat/{intersection_id}/latest")
def latest_heartbeat(intersection_id: str) -> dict:
    """D22: the edge's latest heartbeat, aged by the server's own clock. A
    heartbeat without a source is served with `source` null, which a reader
    must show as unknown, never as live."""
    valid_id(intersection_id)
    with closing(connect()) as connection:
        row = connection.execute("SELECT at, payload FROM heartbeats WHERE intersection_id = ?",
                                 (intersection_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "no heartbeat for this intersection yet")
    payload = decode(Topic.HEARTBEAT, row[1])
    age = time.time() - row[0]
    return {"at": row[0], "age_s": round(age, 1),
            "stale": age > SafetyLimits().mqtt_timeout_s,
            "edge_status": payload.edge_status, "mode": payload.mode.value,
            "source": dict(payload.source) if payload.source else None,
            "lanes": dict(payload.lanes) if payload.lanes else None,
            "directions_verified": payload.directions_verified,
            "note": HEARTBEAT_NOTE}


#: D26: checks arrive one per 2 s step and the page reads the last 20 minutes,
#: so an hour is kept: enough, and bounded without a scheduler.
CHECK_RETENTION_S = 3600
CHECK_SPACING_S = 60
CHECK_SLOTS = 20
AGREEMENT_LABEL = ("Rolling agreement with auto-labels over the last 20 checked minutes. "
                   "Not a benchmark — the observed values come from the same detector counts "
                   "the forecasts are made from. Benchmark figures are in Results.")
AGREEMENT_LIMITS = ("Not accuracy: both sides come from one detector's counts, not "
                    "human-verified traffic. These are the live persistence and ridge "
                    "forecasts, not MFSTNet; this camera and these minutes only; no forecast "
                    "drives a signal (P97a).")


def store_forecast_check(intersection_id: str, raw: str | bytes):
    """Validate one encoded `ForecastCheck` and store it (D26). The single entry
    point over HTTP and over MQTT alike. Checks older than an hour are removed
    on each store, by an indexed range delete."""
    check_intersection_id(intersection_id)
    payload = decode(Topic.FORECAST_CHECK, raw)
    now = time.time()
    with closing(connect()) as connection:
        connection.execute("INSERT INTO forecast_checks VALUES (?,?,?,?,?)",
                           (now, intersection_id, payload.session, payload.made_ts,
                            payload.encode()))
        connection.execute("DELETE FROM forecast_checks WHERE intersection_id = ? AND at < ?",
                           (intersection_id, now - CHECK_RETENTION_S))
        connection.commit()
    return payload


@app.post("/forecast_check/{intersection_id}", dependencies=WRITE)
def forecast_check(intersection_id: str, raw: str = Body(..., media_type="text/plain")) -> dict:
    """One `ForecastCheck`, exactly as the edge encoded it: the HTTP stand-in
    for the MQTT topic, with the same validation."""
    try:
        payload = store_forecast_check(intersection_id, raw)
    except ContractError as error:
        raise HTTPException(422, str(error)) from error
    return {"intersection_id": intersection_id, "session": payload.session}


#: A minute is represented by a check made within this long of its start: the
#: longest step the edge's window keeps (`SampleBuffer.max_gap_s`), so a healthy
#: stream always has one, however its steps jitter. At exactly 2 s a camera's
#: 2.3 s steps drew false gaps. Chosen checks are 60 s apart to within 3 s, so
#: their minutes overlap by at most 3 s of samples.
CHECK_GRID_S = 3.0


def space_checks(checks: list) -> list[dict]:
    """The last `CHECK_SLOTS` minutes of one session, oldest first (D26).

    On a fixed one-minute grid of the edge's own sample time, never of
    arrival: each minute is represented by its first check, made within
    `CHECK_GRID_S` of the minute's start. The grid is absolute, so a cell never
    changes once drawn, whatever arrives later or is pruned. A minute whose
    start has no check (a gap reset the edge's window there) is a gap slot,
    never skipped and never filled, so the row cannot look continuous when it
    was not. The row starts at the first minute with a check, so warming up
    is not drawn as a gap."""
    first: dict[int, object] = {}
    for check in checks:
        minute = int(check.made_ts // CHECK_SPACING_S)
        if check.made_ts - minute * CHECK_SPACING_S < CHECK_GRID_S and (
                minute not in first or check.made_ts < first[minute].made_ts):
            first[minute] = check
    if not first:
        return []
    newest = int(max(c.made_ts for c in checks) // CHECK_SPACING_S)
    slots = []
    for minute in range(max(min(first), newest - CHECK_SLOTS + 1), newest + 1):
        check = first.get(minute)
        slots.append({"kind": "gap"} if check is None else
                     {"kind": "check", "made_ts": check.made_ts, "checked_ts": check.checked_ts,
                      "classes": {a: dict(p) for a, p in check.classes.items()},
                      "counts": {a: dict(p) for a, p in check.counts.items()}})
    return slots


def agreement_summary(slots: list[dict]) -> dict:
    """Per approach, two separate denominators: classes agreed k of n, and the
    mean absolute count difference over n. Never a percentage."""
    out = {}
    for a in APPROACHES:
        cls = [s["classes"][a] for s in slots if s["kind"] == "check" and a in s["classes"]]
        cnt = [s["counts"][a] for s in slots if s["kind"] == "check" and a in s["counts"]]
        if not cls and not cnt:
            continue
        out[a] = {"class": {"agreed": sum(p["forecast"] == p["observed"] for p in cls), "n": len(cls)},
                  "count": {"mean_abs_diff": round(sum(abs(p["forecast"] - p["observed"]) for p in cnt)
                                                   / len(cnt), 2) if cnt else None, "n": len(cnt)}}
    return out


@app.get("/forecast_check/{intersection_id}/recent")
def recent_forecast_checks(intersection_id: str) -> dict:
    """D26, ADR-014 §2: the latest session's checks, a minute apart, with the
    agreement over them. 404 when there are none, which the page reads as
    warming up or not reported, never as agreement or as zero."""
    valid_id(intersection_id)
    with closing(connect()) as connection:
        latest = connection.execute(
            "SELECT at, session FROM forecast_checks WHERE intersection_id = ? "
            "ORDER BY at DESC LIMIT 1", (intersection_id,)).fetchone()
        if latest is None:
            raise HTTPException(404, "no forecast check for this intersection yet")
        rows = connection.execute(
            "SELECT payload FROM forecast_checks WHERE intersection_id = ? AND session = ?",
            (intersection_id, latest[1])).fetchall()
    checks = [decode(Topic.FORECAST_CHECK, r[0]) for r in rows]
    slots = space_checks(checks)
    newest = max(checks, key=lambda c: c.made_ts)
    age = time.time() - latest[0]
    return {"intersection_id": intersection_id, "session": latest[1],
            "age_s": round(age, 1), "stale": age > SafetyLimits().mqtt_timeout_s,
            "class_model": newest.class_model, "count_model": newest.count_model,
            "spacing_s": CHECK_SPACING_S, "slots": slots, "summary": agreement_summary(slots),
            "label": AGREEMENT_LABEL, "limits": AGREEMENT_LIMITS}


RESULTS = Path("experiments/results/bellevue_pilot")
EVIDENCE_LABEL = ("Historical evaluation evidence, computed offline once under a "
                  "pre-registered protocol. Not a live performance guarantee.")
EVIDENCE_LIMITS = [
    "labels are ITD-xl's own future counts, not human-verified traffic (A32)",
    "one Bellevue Sunday evening and Monday; 3 cameras scored; 116th NE12th excluded",
    "a count improvement does not establish a congestion-class improvement",
    # The encoding as it is since P110, as the dashboard's live banner states it.
    "neither forecast is connected to signal timing; in the controller's state 0.0 means "
    "an approach has no forecast and LOW is 1/3 (ADR-020 as amended, P110); P97a Part 2, "
    "the controller's behaviour under forecast faults, is deferred",
]


#: Where a container finds what `git log` would have said (D15). A container
#: has no repository history, so `deploy/evidence_commits.py` writes this map
#: from the real history when the image is built. Unset outside a container.
EVIDENCE_COMMITS_ENV = "STMS_EVIDENCE_COMMITS"


def committed_at(path: Path) -> dict:
    """ADR-014: the panel names the commit that produced each number.

    From `git log` when there is a repository, else from the build-time map.
    Neither available is "uncommitted", never a guess."""
    import subprocess

    name = str(path).replace("\\", "/")
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%h %cs", "--", str(path)],
                             capture_output=True, text=True, timeout=5, check=True).stdout.split()
    except Exception:
        out = []
    if not out and os.environ.get(EVIDENCE_COMMITS_ENV):
        try:
            entry = json.loads(Path(os.environ[EVIDENCE_COMMITS_ENV]).read_text(encoding="utf-8"))[name]
            out = [entry["commit"], entry["date"]]
        except (OSError, ValueError, KeyError, TypeError):
            out = []
    return {"file": name,
            "commit": out[0] if out else "uncommitted", "date": out[1] if len(out) > 1 else ""}


def _row(metric, a_name, a, b_name, b, test=None, lower_is_better=False):
    """A difference is always stated so that positive favours `a_name`."""
    row = {"metric": metric, "lower_is_better": lower_is_better,
           "values": {a_name: round(a, 4), b_name: round(b, 4)},
           "difference_of": (f"{b_name} − {a_name}" if lower_is_better
                             else f"{a_name} − {b_name}"),
           "positive_favours": a_name}
    if test is not None:
        row.update({"difference": test["point"], "ci95": test["ci95"],
                    "significant": bool(test.get("holm_significant"))})
    return row


@app.get("/evidence")
def evidence() -> dict:
    """ADR-014 Panel A: frozen numbers read from committed result files.

    Nothing here is live and nothing changes while the dashboard runs. Every
    value is read from the file named beside it, never typed into the page.
    """
    import json

    def load(name):
        return json.loads((RESULTS / name).read_text(encoding="utf-8"))

    try:
        p105, p103 = load("p105_results.json"), load("p103_results.json")
        excluded = sorted(load("p105_eligibility.json")["excluded_cameras"])
    except FileNotFoundError as error:
        raise HTTPException(503, f"evidence file missing: {error.filename}") from error
    p105_cams = sorted(p105["per_camera"])
    return {
        "label": EVIDENCE_LABEL, "limitations": EVIDENCE_LIMITS,
        "studies": [
            {"id": "P105", "role": "next_minute_count (ridge)",
             "question": "Does the level-free ridge forecast next-minute counts better than persistence?",
             **committed_at(RESULTS / "p105_results.json"),
             "scope": {"cameras": p105_cams, "excluded_cameras": excluded,
                       "windows": p105["windows"], "blocks": p105["blocks"]},
             "rows": [
                 _row("count MAE (vehicles)", "ridge", p105["pooled"]["ridge"]["mae"],
                      "persistence", p105["pooled"]["persistence"]["mae"],
                      p105["primary"]["persistence - ridge, count MAE"], lower_is_better=True),
                 _row("congestion macro-F1", "ridge", p105["pooled"]["ridge"]["f1"],
                      "persistence", p105["pooled"]["persistence"]["f1"],
                      p105["primary"]["ridge - persistence, macro-F1"])]},
            {"id": "P103", "role": "congestion_class (persistence)",
             "question": "Which class forecaster transfers to new cameras?",
             **committed_at(RESULTS / "p103_results.json"),
             "scope": {"cameras": sorted(p103["calibrated"]["per_camera"]),
                       "windows": sum(p103["calibrated"]["support"].values()) // 4,
                       "blocks": p103["primary"]["C1-L - persistence"]["blocks"]},
             "rows": [
                 _row("congestion macro-F1", "persistence", p103["calibrated"]["pooled"]["persistence"]["f1"],
                      "count model C1-L", p103["calibrated"]["pooled"]["C1-L"]["f1"],
                      {**p103["primary"]["C1-L - persistence"],
                       "point": -p103["primary"]["C1-L - persistence"]["point"],
                       "ci95": [-x for x in reversed(p103["primary"]["C1-L - persistence"]["ci95"])]})]},
        ]}


@app.get("/history/{intersection_id}")
def history(intersection_id: str, limit: int = Query(50, ge=1)) -> dict:
    """Recent decisions, for the Live page's event panel (ADR-008, FR-UI0x).

    `limit` is at least 1 (P142): `min(-1, 500)` is -1, and SQLite reads
    `LIMIT -1` as no limit at all. Above 500 it is still clamped, not refused."""
    valid_id(intersection_id)
    with closing(connect()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM observations WHERE intersection_id = ? "
            "ORDER BY at DESC LIMIT ?", (intersection_id, min(limit, 500))
        ).fetchall()
    return {"intersection_id": intersection_id,
            "rows": [dict(row) for row in rows]}


# The read-only dashboard (ADR-008 Live/Results, ADR-014 two panels), served
# from the same origin when it has been built: `npm run build` in dashboard/.
_DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if _DASHBOARD.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/dashboard", StaticFiles(directory=_DASHBOARD, html=True), name="dashboard")
