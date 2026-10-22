# Standard Operating Procedures (SOP)

| | |
|---|---|
| **Wave** | 4 (ADR-004) |
| **Status** | **Draft for review**, 2026-10-22. Not approved |
| **Describes** | Operating the prototype at commit `21c8708` (D7), once it is installed by the [TIM](TIM.md) |
| **Authority** | The [PRD](../00-planning/PRD.md) and the ADRs. Where this procedure and the code disagree, the code is the fact and this procedure is the defect |
| **Audience** | Whoever runs the prototype for a session or a demonstration |

> **What an operator is running.** It is a research prototype that counts
> traffic in a video or camera stream, forecasts congestion, and stores and
> displays those forecasts.
> - **It does not control traffic signals, and nothing here connects to signal
>   hardware.** No forecast feeds signal timing (ADR-027, P97a).
> - **It is not ready for a real intersection.** Four prerequisites are open
>   (TIM §1): teammate access to the detector weights and their licence; a
>   lane file and thresholds for the target camera; an authenticated
>   deployment broker (Mosquitto is untested, and there is no TLS); and the
>   Python and disk constraints.

---

## 1. Start-up

Start in this order. Each step has a check, and a step is not done until its
check passes.

| # | Start | Check |
|---|---|---|
| 1 | **The broker** (TIM §7) | It is listening on its port |
| 2 | **The server**, from the repository root: `python -m uvicorn server.app:app --port 8000` | `GET http://127.0.0.1:8000/health` returns `"status": "ok"` |
| 3 | **The ingest**, with its own credentials in the environment: `python -m server.mqtt_ingest --host 127.0.0.1 --port 1883` | It prints `subscribed to stms/+/congestion/prediction and stms/+/count/forecast on …`. If it exits instead, see §6 |
| 4 | **The edge**, with its own credentials (TIM §9) | Its log shows `source: …` and no `error:` line |
| 5 | **The dashboard** at `http://127.0.0.1:8000/dashboard/?id=<id>` | The page loads. The panels fill once forecasts arrive (§3) |

**Why this order.**
- **The ingest exits** when the broker is missing or refuses it, so the broker
  comes first.
- **The edge does not exit** without a broker: it warns and runs its local
  cycle. Started before the broker, it simply delivers nothing until the
  broker appears.

**Credentials.** Set `STMS_MQTT_USERNAME` and `STMS_MQTT_PASSWORD` in each
program's own terminal. Never type them on a command line, and never put them
in a script or a file in the repository. A warning that a program is
"connecting anonymously" means they are not set. Only a development broker
should accept that.

---

## 2. Shutdown

Stop in the reverse order: edge, then ingest, then server, then broker.

| Program | How | What it does |
|---|---|---|
| Edge | Ctrl+C, or let `--samples N` finish | Logs `interrupted` or `stopped; …`, closes its broker connection and exits 0 |
| Ingest | Ctrl+C | Exits with a Python `KeyboardInterrupt` traceback, without disconnecting from the broker first. **This is expected at `21c8708`** and loses nothing already stored. Read from the code: validation did not send Ctrl+C |
| Server | Ctrl+C | uvicorn shuts down |
| Broker | Stop its process or service | Clients that are still running lose their connection (§5) |

The store, `data\server\stms.sqlite`, persists between sessions. Do not edit it
by hand.

---

## 3. Is it working? Started is not delivered

| Observation | What it shows |
|---|---|
| Edge log: `source: …`, no `error:` | The edge **started** |
| Edge log: `broker … not reachable` or `refused the connection` | It started **without** a connection (§5, §6). `not reachable` at start-up can also mean the broker took longer than the edge's 5 s connection wait. The edge keeps trying, so if forecasts arrive afterwards, it connected |
| `GET /prediction/<id>/latest` returns 200 with `"stale": false` | **Delivery** of a class forecast. The first comes after 30 samples (60 s) |
| `GET /count_forecast/<id>/latest` returns 200 | **Delivery** of a count forecast. The first comes after 60 samples (2 min) |
| `"stale": true` | The newest stored forecast is older than its 60 s horizon: nothing has been delivered since |
| `404 no prediction for this intersection yet` | Nothing delivered yet, or the wrong `--intersection-id` |

**A gap restarts both windows.** A missing sample (the camera reconnecting, a
refused sample) restarts the 30- and 60-sample windows. Forecasts pause for 60
s and 2 min, which is by design: a window is never bridged over a hole.

**What the server cannot see.** The edge publishes a heartbeat with its mode,
but the ingest does not store heartbeats. **The edge's local-cycle mode is
visible only in the edge's own log** (§5), not on the server or the dashboard.

---

## 4. Routine checks during a session

Every 15 minutes, or before anyone relies on what the dashboard shows:

1. **The edge log** has no new `FR-A06` line (§5) and no `sample refused`
   lines (§7).
2. **`GET /prediction/<id>/latest`** shows `"stale": false` and an `age_s`
   under 60.
3. **The ingest's output** has no `ingest refused a message` or
   `ingest failed` lines (§7).
4. **The dashboard** shows both panels, and no stale banner.

---

## 5. Broker disconnection and recovery (FR-A06)

**What the edge does.** It keeps a single piece of link state, `last_ack`: the
time of its last publish the broker acknowledged.
- **More than 10 s after `last_ack`**, it logs
  `FR-A06: no successful publish for N s, over the 10s timeout; running the
  locally embedded cycle` and switches to its local cycle: a fixed 30 s
  alternation that drives no output.
- **The 10 s run from the last acknowledgement, not from the moment the
  broker stopped**, so a stopwatch started at the stop does not read 10 s.
  The line is written at the next 2 s step, after that step's work. Measured
  with this procedure:

  | Run | Since the last acknowledgement (in the line) | From the stop to the line appearing |
  |---|---|---|
  | D3 live run | 12.0 s | 11.6 s |
  | TIM validation, run 4 | 10.2 s | 9.6 s |
  | TIM validation, run 3 | 12.7 s | 19.1 s |

  With nothing ever acknowledged, the 10 s run from when the node started.
- **When the broker returns**, the edge reconnects by itself. On the first
  acknowledged publish it logs `link restored: publishes are acknowledged
  again`. That reports the link only; the server drives no signal (D7).

> **A restored link is not a fresh forecast.** After the broker returns,
> `link restored` can appear within seconds, while the dashboard still shows
> the old forecast. In validation the first freshly stored forecast came up
> to **47.8 s** after the restart, while the ingest reconnected. Do not rely
> on the dashboard again until `/prediction/<id>/latest` shows
> `"stale": false` with a new `at`.

**What the ingest does.** It reconnects and resubscribes by itself when the
broker returns, but **not at once**. Its wait between reconnection attempts
grows the longer the broker is down. After a restart, the first freshly
stored forecast came 8.6 s later in one validation run and 47.8 s later in
another.

**What is lost.** Forecasts made while the link is down are not delivered
later. The edge's transport refuses to publish while disconnected, and nothing
queues them.

**Procedure.**
1. Note the time of the `FR-A06` line. Nothing needs doing on the edge: the
   local cycle is the designed behaviour.
2. Restore the broker.
3. Confirm `link restored` in the edge log.
4. Confirm the ingest is still running. If it exited, restart it (§1, step 3).
5. Wait for `"stale": false` on `/prediction/<id>/latest`. That took up to
   48 s in validation, while the ingest reconnected, and it takes longer if
   the edge's windows restarted.

---

## 6. Authentication failures

| Message | Cause | Action |
|---|---|---|
| Ingest exits (code 1): `the broker at … refused the connection: Not authorized` | Missing, wrong or unknown credentials | Check that both variables are set in that terminal, and that the user is in the broker's password file. Restart the ingest |
| Edge: `broker … refused the connection (Not authorized)` | The same | Fix it as above, then restart the edge. Until then it runs its local cycle |
| Edge: `error: STMS_MQTT_USERNAME is set but STMS_MQTT_PASSWORD is not` (or the reverse), exit code 2. Ingest: the same text without `error:`, exit code 1 | Half a credential | Set both |
| `connecting anonymously` warning | Neither variable set | Acceptable only against a development broker |

**No message prints a credential.** Each names the variable, or gives the
broker's reason code. If a password ever appears in output, treat it as §9.3.

---

## 7. Malformed and refused messages

| Where | What you see | Meaning | Action |
|---|---|---|---|
| Ingest | `ingest refused a message on <topic>: ContractError, N bytes` | A payload the contract refuses: a wrong schema, field, size or id (P140–P142). It is not stored, and its content is never logged | Find the sender by the topic's intersection id. An unrouted topic is shown as `<unrouted topic>`. Do not retry the message |
| Ingest | `ingest failed to process a message on <topic>: <error type>, N bytes` | A valid message the server could not process, a locked database say. The ingest keeps running | Check disk and the database file. Restart the server if it persists |
| Edge | `counts for <lane> withheld: …` | A detector class with no mapping (D1). That lane's count is not published | Check `itd_mapping` in `class_mapping.yaml` against the detector |
| Edge | `sample refused by <forecaster>: …` | A sample with a missing lane or an invalid count. It is dropped, and the next sample restarts the window | Check the lane file and the approach mapping |
| HTTP | `422` with the error type and location only | A request the server refuses. The response does not echo the input (P142) | Fix the caller |

---

## 8. Logs

- **Where.** Each program writes to its own terminal: the edge through
  Python logging, the ingest by printing, and uvicorn its access log. **No
  program writes a log file**, so a session's log lasts as long as its
  terminal. Copy the lines you need for a record.
- **What the logs never contain:** frames (NFR-13), the camera URL,
  credentials, refused payload contents, and paths the server did not route
  (P142).
- **The lines to know.**

  | Program | Line | Meaning |
  |---|---|---|
  | Edge | `source: …` | Started |
  | Edge | `no MQTT credentials set; connecting anonymously …` | No credentials (§6) |
  | Edge | `broker … not reachable` / `refused the connection (…)` | Not delivering (§5, §6) |
  | Edge | `FR-A06: no successful publish for …` | Local cycle (§5) |
  | Edge | `link restored; …` | Publishes acknowledged again (§5) |
  | Edge | `camera stream ended; reconnecting` | Camera source lost; it retries by itself |
  | Edge | `stopped; N sample(s) refused …, excluded classes {…}` | Clean end, with what was dropped |
  | Ingest | `subscribed to … and … on …` | Connected, to both forecast topics |
  | Ingest | `ingest refused …` / `ingest failed …` | §7 |

---

## 9. Incident response

### 9.1 The table

| Incident | Immediate action | Keep as a record |
|---|---|---|
| Edge in local cycle | §5 | The `FR-A06` and `link restored` times |
| Ingest exited | Restart it (§1, step 3); if it was refused, §6 | Its last lines |
| Forecasts stale, edge says nothing | Check the ingest is running, then the broker | `age_s` from `/latest` |
| Edge crashed (a Python traceback) | Restart it. Its windows restart, so forecasts resume after 60 s and 2 min | The traceback, without the command line if it holds a path you would not share |
| Camera lost | Nothing; the edge retries the stream by itself and its local cycle keeps running | The `camera stream ended` times |
| Disk full | Stop the edge and the server. Free space; do not delete `data\server\stms.sqlite` | Free space on each drive |
| **A credential exposed** | §9.3 | Where it appeared |
| **A frame or video written to disk** | §9.4 | The file's path and time, not the file |

### 9.2 Restarting safely

Restart in the §1 order. After a restart, confirm §3 delivery again before
relying on the dashboard. Never point two edges at the same intersection id.
Never edit the store by hand.

### 9.3 A credential exposed

A credential counts as exposed if it appeared on a command line, in a log, a
screenshot, a chat or a file in the repository.
1. **Revoke it at the broker.** For amqtt, replace the user's line in the
   password file and restart the broker. For Mosquitto, use `mosquitto_passwd`
   (TIM §7.3, unverified with this code).
2. **Set the new password** in that program's environment, and restart the
   program.
3. **If it reached a file in git**, removing it in a later commit does not
   remove it from history. Tell the project owner before anything is pushed.

### 9.4 A frame written to disk (NFR-13)

The edge never writes frames, and D3 and D4 tested that. If an image or video
file of the live scene appears anyway:
1. Stop the edge.
2. Delete the file. Do not copy it anywhere first.
3. Record the path and time, and tell the project owner.

---

## 10. Demonstration day (PRD R9)

PRD §19's risk R9 is MQTT instability during the demonstration. Its
mitigations are a pre-test 48 h before, and a pre-recorded video as backup.

**48 hours before.**
1. Run TIM §12 in full on the demonstration machines, on the network that
   will be used.
2. Stop the broker for 30 s, and confirm §5 end to end: the local-cycle line,
   then `link restored`, then fresh forecasts.

**The backup.**
- Run the edge on a recorded video with `--realtime`. It behaves like a
  camera at one sample per 2 s.
- **Use only footage whose licence permits showing it.** The Bellevue footage
  is for internal engineering use only, and its licence is unresolved.

**On the day.**
1. Follow §1, then wait for the first fresh forecast (60 s) before presenting.
2. Present the dashboard as **forecasts that are stored and displayed**. It
   is not signal control, and not a measured traffic improvement.
3. If the broker fails, §5 is the demonstration of FR-A06, not a fault to
   hide.

---

## 11. Never

- Never put a credential or the camera URL on a command line, in a script, or
  in a file in the repository.
- Never start uvicorn with `--host 0.0.0.0`: the HTTP API has no
  authentication (TIM §8).
- Never describe the prototype as controlling signals, or as ready for a real
  intersection.
- Never redistribute the detector weights or licence-restricted footage.
- Never edit `data\server\stms.sqlite` by hand.

---

**Sources:** the [TIM](TIM.md); the SAD and HLD (`docs/02-design/`);
Execution Manual §0.7 and §5.3; PRD-CHANGELOG P140 to P142, and D1 to D6.
