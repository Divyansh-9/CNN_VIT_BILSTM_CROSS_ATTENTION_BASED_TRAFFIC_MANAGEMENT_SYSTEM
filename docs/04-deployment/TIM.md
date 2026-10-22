# Transition and Implementation Manual (TIM)

| | |
|---|---|
| **Wave** | 4 (ADR-004) |
| **Status** | **Draft for review**, 2026-10-22. Not approved |
| **Describes** | Installing the prototype from the repository at commit `21c8708` (D7) |
| **Validated by** | A script that followed it literally in a fresh clone of `0e86119`, which differs from `21c8708` only in D7's message changes, against an authenticated amqtt broker, 2026-10-22 (§12.1). **Not yet followed by a person on a machine that has never run the project**, which is what [the deployment README](README.md) asks for |
| **Authority** | The [PRD](../00-planning/PRD.md) and the ADRs. Where this manual and the code disagree, the code is the fact and this manual is the defect |
| **Audience** | A team member installing the prototype on a Windows laptop |

> **This installs a research prototype. It is not a deployment to a real
> intersection.**
> - **Nothing here connects to signal hardware.** The server's command endpoint
>   proposes phases with a placeholder rule, and no forecast feeds signal
>   timing (ADR-027, P97a).
> - **The edge's local cycle is a fixed 30 s alternation that drives no
>   output.** It is FR-A06's fallback behaviour, logged and nothing more.
> - **Four prerequisites are not in the repository** (§1). Until they are
>   resolved, a teammate cannot complete this installation from the repository
>   alone.

---

## 1. Four prerequisites the repository does not provide

| # | Prerequisite | State at `21c8708` | Owner |
|---|---|---|---|
| 1 | **Detector weights**, `models/external/best_xl_ITD_v1.2.pt` | Not distributed: `models/` is gitignored. The only copy is the project owner's private backup (S66). Third-party weights, **licence unresolved**: do not publish or redistribute them | Project owner |
| 2 | **Camera configuration**: a reviewed lane file and calibrated thresholds for the target camera | No committed lane file belongs to a camera in the persistence spec. **No committed command calibrates a new camera into the spec**: `scripts/persistence_freeze.py` regenerates the frozen spec for its four known cameras only | Team |
| 3 | **An authenticated deployment broker** | Both clients send credentials (D6), verified against an authenticated amqtt broker. **Mosquitto is not tested, and no broker configuration is committed. There is no TLS** | Team |
| 4 | **The environment**: Python 3.12 and disk space | `py -3.12` needs a Python 3.12 install. About 9 GB free: pip's cache took 3.1 GB and the environment 6.0 GB (measured) | Each machine |

§5, §6 and §7 say what to do about 1, 2 and 3 today, and what is not possible
yet.

---

## 2. What gets installed, and where

```
 laptop (ADR-003)                                            same laptop, or a second one
 ┌──────────────────────────────┐   MQTT 1883   ┌────────┐   MQTT   ┌───────────────────────────┐
 │ python -m edge.run           │──────────────▶│ broker │─────────▶│ python -m server.mqtt_ingest │
 │  video file or camera (RTSP) │  credentials  └────────┘          │        │ store (SQLite)   │
 │  detector → counts →         │  from env                         │ uvicorn server.app:app    │
 │  persistence + ridge         │                                   │  HTTP :8000 ──▶ dashboard │
 └──────────────────────────────┘                                   └───────────────────────────┘
 frames stay here (NFR-13)                                           read-only, GET only
```

| Component | Installed from | Runs as |
|---|---|---|
| Python environment | `requirements.txt` (§4) | `.venv` in the clone |
| Edge program | the repository | `python -m edge.run` (§9) |
| MQTT broker | **not in `requirements.txt`** (§7) | its own process |
| Server and ingest | the repository | two processes (§8) |
| Dashboard | `dashboard/`, built with Node (§10) | static files served by the server |

**Not committed, despite older text that says so:** a Docker Compose file
(D4). Nothing in this manual uses Docker.

---

## 3. Machine requirements

| Item | Requirement | Tested with |
|---|---|---|
| Operating system | Windows 11 | Windows 11 Home 10.0.26200 |
| Python | **3.12**, the version CI runs (D4) | 3.12.10; 3.14.4 also passed |
| Git | any recent version | git with Git LFS 3.6.1 (LFS is not needed for this manual) |
| Node.js | for building the dashboard only (§10) | v24.15.0 |
| Disk | **about 9 GB free**: pip's download cache and the environment | cache 3.1 GB, environment 6.0 GB (measured) |
| GPU | optional. The detector uses the GPU when PyTorch sees one | RTX 4050 Laptop, 6 GB. CPU-only operation is not measured |
| Free ports | 1883 (broker), 8000 (server) | |

---

## 4. Get the code and the Python environment

```powershell
git clone <repository URL> stms
cd stms
git checkout 21c8708                  # the commit this manual describes

python scripts/check_env.py           # stdlib only: runs before anything is installed
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch==2.13.0+cu126 torchvision==0.28.0+cu126 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
python scripts/check_env.py           # expect "No blockers"
python scripts/check_sim_versions.py  # expect "simulation stack matches requirements.txt"
```

- **`py -3.12` fails?** Python 3.12 is not installed. Install it from
  python.org; it coexists with other versions. `py -0` lists what is installed.
- **Short of disk on the system drive?** Before the two `pip install`
  commands, point pip's cache and temporary files at a drive with room:

  ```powershell
  $env:PIP_CACHE_DIR = "D:\pip-cache"; $env:TMP = "D:\tmp"; $env:TEMP = "D:\tmp"
  ```

- **Use the `cu126` index.** `cu121` and `cu124` carry no torch at any
  version, and the failure looks like a network problem (P32).
- **Two expected warnings from `check_env.py`:** 6 GB of VRAM is too small
  for *uncached* MFSTNet training (irrelevant here), and Shapely is not
  installed (nothing imports it).

---

## 5. Detector weights (prerequisite 1)

The edge counts with `best_xl_ITD_v1.2.pt`. Its path, with the confidence
threshold (0.45) and input size (992), is read from the `counting` block of
`indiatrafficnet/class_mapping.yaml` (D5).

1. **Obtain the file.** Today the only copy is the project owner's private
   backup (`trained_weight.zip`, S66). Ask the owner. **Do not publish,
   upload or redistribute it**: it is third-party, and its licence is
   unresolved.
2. **Place it** at `models\external\best_xl_ITD_v1.2.pt`.
3. **Verify it** against the committed manifest. The two hashes must be
   identical:

   ```powershell
   (Get-FileHash models\external\best_xl_ITD_v1.2.pt -Algorithm SHA256).Hash.ToLower()
   Select-String "best_xl_ITD_v1.2.pt" experiments\results\model_artifacts.sha256
   ```

   Expected: `06006ecb5fe52a348ceed805bf0aa6b32af7e24e689d09a6582f6d53159d6b00`.

`python scripts/backup_models.py check` is **not** the right tool for one
file. It checks all 301 artifacts the manifest lists, and reports the other
300 as gone from disk.

---

## 6. Camera configuration (prerequisite 2)

The edge needs three things that belong to one camera:

| Item | Where it comes from | Checked at start-up |
|---|---|---|
| **Lane file** | `docs/demo/place_lanes.html` to place the lane centres by hand, then `python scripts/import_lane_centres.py` (Execution Manual §2.3). A corpus manifest built from that camera also works | It must say `"reviewed": true`, or be a corpus manifest. Automatic centres are never used (P23) |
| **Approach mapping** | Which lane is N, S, E or W, from looking at the camera | Every lane mapped once, to a distinct approach |
| **Thresholds** | The camera's key in `experiments/results/bellevue_pilot/persistence_v1.json` | The key must exist, and its lane count must equal the lane file's |

**What is not possible today:**
- **No committed lane file belongs to a camera in the spec.**
- **No committed command adds a new camera's thresholds.** The spec is frozen
  (its hash is the model id), and `scripts/persistence_freeze.py` rebuilds it
  for its four known cameras only. A new camera needs a calibration hour
  (ADR-017) and a new, reviewed freeze.

**For an installation check only,** the committed 4-lane
`data/corpus/manifest.json` with `--camera 150th_Eastgate` (also 4 lanes)
starts the program. It is not that camera's geometry, so its forecasts mean
nothing.

---

## 7. The MQTT broker (prerequisite 3)

### 7.1 Credentials

Both clients read the same two environment variables (D6). Set them in the
shell that starts each program, never on its command line:

```powershell
$env:STMS_MQTT_USERNAME = "edge-ne8th"
$env:STMS_MQTT_PASSWORD = "..."     # from wherever the team keeps secrets; never in git
```

- **Both or neither.** One without the other stops the program at start-up
  with an error that names the missing variable and quotes no value.
- **Neither** means an anonymous connection. Each program warns that only a
  development broker should accept it.
- **Use one user per program**, for example `edge-ne8th` and `stms-ingest`, so
  one can be revoked without the other.

### 7.2 The tested broker: amqtt (development and verification)

This is the broker D6 verified authentication against. It is **not** a
project dependency: install it in a separate environment, so its
dependencies never meet the project's.

```powershell
py -3.13 -m venv C:\stms-broker
C:\stms-broker\Scripts\pip install amqtt==0.12.1      # brings pwdlib for Argon2 hashes
```

`broker.yaml`, with anonymous access off:

```yaml
listeners:
  default:
    type: tcp
    bind: 127.0.0.1:1883
plugins:
  amqtt.plugins.authentication.AnonymousAuthPlugin:
    allow_anonymous: false
  amqtt.plugins.authentication.FileAuthPlugin:
    password_file: C:/stms-broker/passwords
```

`passwords` holds one `username:hash` line per user. Make each hash with the
broker's own hasher (amqtt requires `pwdlib[argon2]`, so it is already
installed). The password is typed at a prompt that does not echo it. **The
prompt is interactive**: on Windows it reads the keyboard directly, so it
cannot be scripted or piped:

```powershell
C:\stms-broker\Scripts\python -c "import getpass; from pwdlib.hashers.argon2 import Argon2Hasher; print(Argon2Hasher().hash(getpass.getpass()))"
C:\stms-broker\Scripts\amqtt -c broker.yaml
```

Keep `passwords` out of the repository.

### 7.3 The deployment broker: Mosquitto (not verified)

PRD §17 names Mosquitto. **It has not been tested with this code, and no
Mosquitto configuration is committed.** The standard Mosquitto 2 settings for
NFR-11 are below. They are Mosquitto's documented mechanism, **not a
configuration this project has run**:

```
listener 1883 127.0.0.1
allow_anonymous false
password_file C:\mosquitto\passwd
```

```powershell
mosquitto_passwd -c C:\mosquitto\passwd edge-ne8th    # prompts for the password
mosquitto_passwd C:\mosquitto\passwd stms-ingest
```

**Before relying on it**, run §12 against it, including the refusal checks.
Until then, Mosquitto compatibility is an open item, not a fact.

### 7.4 No TLS

Credentials and payloads cross the network in clear text over plain TCP.
NFR-11 asks for username and password authentication; encrypting the link has
not been decided. Keep the broker on `127.0.0.1` or a trusted LAN.

---

## 8. Server and ingest

Start both **from the repository root**: the store is `data\server\stms.sqlite`,
a path relative to the working directory.

```powershell
python -m uvicorn server.app:app --port 8000                 # HTTP; 127.0.0.1 by default
$env:STMS_MQTT_USERNAME = "stms-ingest"; $env:STMS_MQTT_PASSWORD = "..."
python -m server.mqtt_ingest --host 127.0.0.1 --port 1883     # a second terminal
```

| You see | Meaning |
|---|---|
| `subscribed to stms/+/congestion/prediction and stms/+/count/forecast on 127.0.0.1:1883` | The ingest is connected to both forecast topics (D7) |
| `the broker at … refused the connection: Not authorized` (exit code 1) | Wrong, missing or unknown credentials |
| `STMS_MQTT_USERNAME is set but STMS_MQTT_PASSWORD is not; …` (exit code 1) | Half a credential. Unlike the edge, the ingest exits with code 1 and no `error:` prefix |
| `could not subscribe at …` (exit code 1) | No broker on that host and port |

**The HTTP API has no authentication.** NFR-12 asked for a JWT login, and
ADR-008 replaced it with a shared password; neither is implemented. Its write
endpoints (`POST /observation`, `POST /prediction/{id}`,
`POST /count_forecast/{id}`) accept any caller. **Keep uvicorn on
`127.0.0.1`**, its default, and do not pass `--host 0.0.0.0`.

---

## 9. The edge program

```powershell
$env:STMS_MQTT_USERNAME = "edge-ne8th"; $env:STMS_MQTT_PASSWORD = "..."
python -m edge.run --source clip.mp4 --lanes lanes.json --approaches lane_0=W lane_1=N lane_2=E `
    --camera NE8th --intersection-id ne8th --broker-host 127.0.0.1 --broker-port 1883
```

| Argument | Meaning |
|---|---|
| `--source` | A video file, or `camera`, which reads the stream URL from `STMS_CAMERA_URL`. Set the URL in the environment, never on the command line |
| `--lanes` | The reviewed lane file, or a corpus manifest (§6) |
| `--approaches` | Every lane once, each to a distinct `N`, `S`, `E` or `W` |
| `--camera` | The camera's key in the persistence spec |
| `--intersection-id` | 1 to 32 characters from `A-Z a-z 0-9 _ -` (P142) |
| `--broker-host`, `--broker-port` | Default `127.0.0.1`, `1883` |
| `--weights`, `--conf`, `--imgsz` | Default to the `counting` block of `class_mapping.yaml` (D5). Changing them invalidates the thresholds |
| `--persistence-spec`, `--ridge-spec` | Default to the frozen specs in `experiments/results/bellevue_pilot/` |
| `--samples N` | Stop after N samples of 2 s |
| `--realtime` | Pace a video file at one sample per 2 s, as a camera would |

Anything invalid stops the program at start-up with exit code 2 and one
`error:` line. That covers a bad argument, a missing file, an unreviewed lane
file, mismatched thresholds, half a broker credential, `--source camera`
without `STMS_CAMERA_URL`, and a `counting` block missing a setting.

---

## 10. The dashboard

```powershell
cd dashboard
npm install            # exact versions are pinned in package.json
npm run build          # writes dashboard\dist, which the server serves at /dashboard
cd ..
```

**Restart the server after the first build.** It mounts `/dashboard` only if
`dashboard\dist` exists when it starts. Then open
`http://127.0.0.1:8000/dashboard/?id=<intersection id>`.

The dashboard is read-only (GET only) and has no login.

---

## 11. Start-up order

1. The broker (§7).
2. The server, then the ingest (§8). **The ingest exits** if the broker is
   missing or refuses it, so the broker comes first.
3. The edge (§9). The edge **does not exit** without a broker: it warns, and
   FR-A06's local cycle takes over 10 s after the last acknowledged publish.
4. The dashboard (§10).

The SOP covers daily operation, shutdown and recovery.

---

## 12. Installation check

Run it after every installation. Each line separates **started** from
**delivered**.

| # | Check | Expected |
|---|---|---|
| 1 | `python scripts/check_env.py`; `python scripts/check_sim_versions.py` | "No blockers"; "simulation stack matches requirements.txt" |
| 2 | The weights hash (§5) | Equal to the manifest's |
| 3 | `python -m edge.run --help` | Exit 0 |
| 4 | `GET http://127.0.0.1:8000/health` | `{"status": "ok", "limits": …}` |
| 5 | **NFR-11, refused:** start the ingest with **no** credentials set | Exit code 1: `the broker at … refused the connection: Not authorized` |
| 6 | **NFR-11, accepted:** start the ingest with its credentials | `subscribed to …` in its terminal |
| 7 | Start the edge (§9) on a test video with `--realtime` | Log: `source: …`, no `error:`. This shows it **started**, nothing more |
| 8 | After 60 s: `GET /prediction/<id>/latest` | 200, with `"stale": false`. This is **delivery** of a class forecast. Measured: 63.0 s after the edge started |
| 9 | After 120 s: `GET /count_forecast/<id>/latest` | 200. The count forecast needs a 2-minute window. Measured: 122.1 s |
| 10 | The dashboard at `/dashboard/?id=<id>` | Both panels populated |

For a check without a real camera, use the §6 installation fixture and any
licensed test video. **The forecasts from it are not evidence of anything.**

### 12.1 How this manual was validated (2026-10-22)

A script followed §4 to §12 literally in a fresh clone of `0e86119` (before
D7's message changes, so it saw their old wording), with
the environment §4's commands had installed. It used the amqtt broker of
§7.2 with anonymous access off, random passwords, a synthetic test video,
and the §6 installation fixture. The script and its outputs are held with
the review evidence, outside the repository.

| Result | Steps |
|---|---|
| **Passed** | §4 pre-flight checks; §5 hash commands (equal to the manifest); §10 `npm install` and `npm run build`, then `/dashboard/` 200; §8 server, `/health` 200; §12 checks 1–10. Refusals: an anonymous ingest (`Not authorized`, exit code 1), half a credential at the ingest (exit code 1) and at the edge (exit code 2), and a wrong edge password (logged, local cycle). The first class forecast came at 63.0 s and the first count forecast at 122.1 s. The only new file was the server's store, and no password appeared in any log |
| **Corrected after the run** | The disk requirement (§1, §3); the ingest's exit codes and messages (§8); that the hash prompt is interactive (§7.2) |
| **Not established** | §7.2's interactive hash prompt, which cannot be scripted (the same hasher was fed from standard input instead); §7.3 Mosquitto; a camera stream; a first-time installation by a person; CPU-only operation |

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `py -3.12` not found | No Python 3.12 installed | Install it from python.org (§4) |
| `No matching distribution found for torch` | Wrong index | Use the `cu126` command exactly (§4) |
| pip fails with a full disk | pip's cache is on a full drive | Redirect `PIP_CACHE_DIR`, `TMP`, `TEMP` (§4) |
| `check_sim_versions.py` reports a mismatch | A SUMO package drifted, for example `sumo-data` (D4) | `pip install -r requirements.txt` again |
| Weights hash differs | Wrong or damaged file | Get the file again from the owner (§5) |
| `error: --lanes …: … not a reviewed lane file` | Unreviewed automatic centres | Place and import them (§6) |
| `error: --camera … has no thresholds` / `was calibrated on N lanes` | No calibration for this camera, or the wrong lane file | §6; there is no committed command for a new camera |
| `error: STMS_MQTT_USERNAME is set but STMS_MQTT_PASSWORD is not` (or the reverse) | Half a credential | Set both, or neither for a development broker |
| `broker … refused the connection (Not authorized)` (edge) | Wrong or unknown credentials | Check the user exists in the broker's password file |
| `broker … not reachable` (edge) | No broker on that host and port | Start the broker; the edge connects when it appears |
| `404 no prediction for this intersection yet` | Fewer than 30 samples delivered, or a different id | Wait 60 s; check `--intersection-id` |
| `"stale": true` | Nothing delivered for longer than the forecast horizon (60 s) | See the SOP, broker disconnection |
| `/dashboard` 404 | The server started before `dashboard\dist` existed | Restart the server (§10) |

---

## 14. Removal and rollback

- **Rollback:** `git checkout <previous commit>` and
  `pip install -r requirements.txt`. Keep a copy of `data\server\stms.sqlite`
  before switching; whether an older commit reads a newer store has not been
  checked.
- **Removal:** delete the clone (with `.venv` and `data\server`), the broker
  environment and its password file. Nothing is installed system-wide except
  Python, Node and, if used, Mosquitto.

---

## 15. What this manual has not established

- **Real-intersection operation.** No camera stream at deployment resolution
  has been qualified (S65). No signal hardware is connected.
- **Mosquitto compatibility and an authenticated deployment broker**
  (prerequisite 3).
- **CPU-only latency.** Every edge figure so far was measured on the RTX 4050
  laptop (ADR-003).
- **A first-time installation by someone else.** The deployment README asks
  for this manual to be validated on a machine that has never run the
  project. That has not been done.

**Sources:** the SAD and HLD (`docs/02-design/`); Execution Manual §0.3, §0.7
and §5.3; PRD-CHANGELOG D3 to D6.
