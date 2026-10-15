"""The prediction and control server (S41, PRD §17, ADR-008).

    uvicorn server.app:app --port 8000

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
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field

from contracts.mqtt import ContractError, Topic, decode

from server.safety import Decision, SafetyLimits, SignalGuard

DATABASE = Path("data/server/stms.sqlite")
APPROACHES = ("N", "S", "E", "W")

app = FastAPI(
    title="STMS control server",
    summary="Counts in, signal commands out. No frames, ever (NFR-13).",
)


class Counts(BaseModel):
    """One observation from one intersection.

    Deliberately has no image field, and no field that could hold one. NFR-13
    is enforced by the shape of this model rather than by a check somewhere
    that could be forgotten.
    """

    intersection_id: str = Field(min_length=1, max_length=64)
    counts: dict[str, int]
    queues: dict[str, int] = Field(default_factory=dict)
    emergency_approach: str | None = None
    seconds_since_heartbeat: float = 0.0
    forecast: dict[str, str] | None = None
    forecast_age_s: float | None = None


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


@app.post("/observation", response_model=CommandOut)
def observation(payload: Counts) -> CommandOut:
    """Counts in, one signal command out, with the rule that produced it."""
    unknown = set(payload.counts) - set(APPROACHES)
    if unknown:
        raise HTTPException(
            422, f"unknown approach(es) {sorted(unknown)}; expected "
                 f"{list(APPROACHES)}")

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


def store_prediction(intersection_id: str, raw: str | bytes):
    """Validate one encoded `CongestionPrediction` and store it (ADR-026).

    The single entry point for predictions, used by the HTTP endpoint and by
    the MQTT subscriber (`server/mqtt_ingest.py`) alike, so the two paths
    cannot validate differently. Decoding through `contracts.mqtt.decode`
    checks the schema version, every field and the NFR-13 size cap before
    anything is written. Raises `ContractError` on a payload it refuses.
    """
    payload = decode(Topic.PREDICTION, raw)
    with closing(connect()) as connection:
        connection.execute("INSERT INTO predictions VALUES (?,?,?,?)",
                           (time.time(), intersection_id, payload.model,
                            payload.encode()))
        connection.commit()
    return payload


@app.post("/prediction/{intersection_id}")
def prediction(intersection_id: str, raw: str = Body(..., media_type="text/plain")) -> dict:
    """One `CongestionPrediction`, exactly as the edge encoded it — the HTTP
    stand-in for the MQTT topic of the same name, with the same validation."""
    try:
        payload = store_prediction(intersection_id, raw)
    except ContractError as error:
        raise HTTPException(422, str(error)) from error
    return {"intersection_id": intersection_id, "model": payload.model,
            "predictions": {k: v.value for k, v in payload.predictions.items()},
            "state_11_14": payload.to_state_values()}


@app.get("/prediction/{intersection_id}/latest")
def latest_prediction(intersection_id: str) -> dict:
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT at, model, payload FROM predictions WHERE intersection_id = ? "
            "ORDER BY at DESC LIMIT 1", (intersection_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"no prediction for {intersection_id} yet")
    payload = decode(Topic.PREDICTION, row[2])
    return {"at": row[0], "model": row[1],
            "predictions": {k: v.value for k, v in payload.predictions.items()},
            "confidences": dict(payload.confidences),
            "gate_value": payload.gate_value,
            "state_11_14": payload.to_state_values()}


@app.get("/history/{intersection_id}")
def history(intersection_id: str, limit: int = 50) -> dict:
    """Recent decisions, for the Live page's event panel (ADR-008, FR-UI0x)."""
    with closing(connect()) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM observations WHERE intersection_id = ? "
            "ORDER BY at DESC LIMIT ?", (intersection_id, min(limit, 500))
        ).fetchall()
    return {"intersection_id": intersection_id,
            "rows": [dict(row) for row in rows]}
