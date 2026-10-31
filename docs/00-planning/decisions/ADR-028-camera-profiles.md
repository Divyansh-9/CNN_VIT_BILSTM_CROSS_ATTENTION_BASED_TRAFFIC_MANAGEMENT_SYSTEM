# ADR-028 — One profile per camera, with evidence bound to what it was measured on

**Status:** Accepted by the project owner 2026-10-31, and implemented (D31). This is **not a faculty-guide signature**. · **Date:** 2026-10-31 · **Follows [D30](../PRD-CHANGELOG.md), and leaves [ADR-027](ADR-027-forecasting-roles.md) unchanged**

## Context

STMS should be something another team can deploy on its own cameras. Today what makes a
camera runnable is scattered, and part of it is not recorded at all.

| Fact | Where | Consequence |
|---|---|---|
| Lane geometry for running exists on one machine | `data/corpus_p103/<camera>/manifest.json`, untracked | A fresh clone cannot run any camera |
| Lanes are centres plus a reach | `lane_centres`, `max_radius`; a detection joins the nearest centre (`assign_to_lane`) | A profile must not promise polygons |
| Thresholds are in a frozen spec | `persistence_v1.json`; the model id is the hash of that file | Adding a camera to it would change the id of every forecast |
| The edge takes its spec as an argument | `--persistence-spec`, `load_spec(path)` | A new camera needs no new edge logic |
| The lane map is arbitrary | P103 Amendment 1: centres "ordered left to right", "Approaches are unnamed" | `lane_0=N` means only "the leftmost is called N" |
| Known weaknesses are in a document | P103 Amendment 1: Newport lane_2 under the signal housing, Eastgate lane_1 over parked vehicles, Eastgate low sun | Nothing that runs the camera knows them |
| Forecasts are keyed N, S, E, W | `contracts/mqtt.py`, and the policy's state slots | Renaming them is a contract change |
| The server holds no camera files | `deploy/server.Dockerfile` | The dashboard can only learn verification from the edge |

## Decision

**1. One committed file per camera, `cameras/<camera_id>.json`, which references and never copies.**

```json
{
  "schema_version": 1,
  "camera_id": "150th_Eastgate",
  "geometry": { "coordinates": "normalised_image", "max_radius": 0.25,
                "lanes": [{ "name": "lane_0", "centre": [0.207, 0.7197] }] },
  "lane_map": { "lane_0": "N" },
  "calibration": { "persistence_spec": "experiments/results/bellevue_pilot/persistence_v1.json",
                   "spec_sha256": "...", "key": "150th_Eastgate" },
  "limitations": ["Lane 1 covers a roof and a parking area, so parked vehicles count"],
  "provenance": { "placed_by": "project owner", "how": "calibration-hour frames", "record": "PREREGISTRATION_P103.md, Amendment 1" },
  "direction": { "status": "declared", "lanes": {} },
  "evidence": []
}
```

Thresholds stay in the spec, reached by path and hash: a copy would be a second source of
truth for a number the model id depends on. A stream URL never goes in a profile, because it
can carry credentials, and neither does a source. A camera and what feeds it are separate
choices, checked together by `check_deployment.py`.

**2. A new camera gets a new spec file, and `persistence_v1.json` never changes.** Its model id
then differs, which is correct: different thresholds are a different forecaster. Published
evidence keeps its ids. The ridge spec stays frozen and shared. It is level-free by design
(P103, P105), measured on three cameras, so transfer to a new one is a claim to test.

**3. Evidence is bound by hash to what it depends on, and status is derived, never stored.** A
stored status goes stale silently. Hashes are SHA-256 of canonical JSON (keys sorted, no
whitespace, UTF-8), so equivalent files hash alike.

| Status | How it is known | Bound to |
|---|---|---|
| Configured, valid, calibrated | Computed on every read, by the edge's validator | Nothing stored |
| Direction verified | Recorded evidence | `geometry`, `lane_map` |
| Replay tested | Recorded evidence | `geometry`, `calibration` |
| Live qualified | Recorded evidence from S65 only, under its pre-registered criteria | `geometry`, `calibration` |

Changing a lane map voids direction evidence and leaves replay evidence standing, because
which letter a lane carries does not change what was counted. No level implies another.

**4. Directions.** `direction.status` is one of:
- **`declared`:** the map is a label, which is every camera today;
- **`verified`:** someone looked, and evidence matches the active configuration;
- **`does_not_apply`:** someone looked, and the lanes are not one per approach, for example
  two regions of one road.

The letters stay, because they are contract keys. The edge reports `directions_verified` on the
heartbeat, optional and read as false when absent. It must come from the edge because the server
holds no camera files. Unless it is true the dashboard shows: "N, S, E and W are labels. Their
directions have not been verified for this camera."

**5. One way in.** `edge.run --profile cameras/x.json` expands to the existing flags and goes
through the same `parse_args`, so there is one set of rules. Every existing flag keeps working.
`demo_live`, `demo_launcher` and `check_deployment` read profiles through one loader.

**6. Lane positions are committed, and publication stays a separate gate.** They are already in a
pushed commit (`656233b`, P103 Amendment 1), in a private repository, so a profile discloses
nothing new. This is not a finding that they are free to publish: P103 records the footage's
licence as unresolved and not publishable, and these numbers were placed by looking at it. Making
the repository public (ADR-013) stays blocked on that question, with the other Bellevue-derived
files.

## Adding a camera, once this exists

1. Place lanes by hand (`docs/demo/place_lanes.html`, `import_lane_centres.py`).
2. Count a calibration period that nothing will later be scored on (ADR-017).
3. Calibrate (`edge.persistence.calibrate`) into a new spec file. **This step has no script yet.**
4. Write the profile, then run `check_deployment.py`.
5. Look at the footage, and record direction evidence.
6. Run a replay, and record that.
7. A live stream goes through S65's criteria.

A new camera therefore costs a person's time and a calibration period by design. That is why an
arbitrary video cannot simply be accepted.

## Acceptance criteria

| Requirement | Test |
|---|---|
| Profile validation | A missing, malformed or unsupported profile fails with a specific diagnostic |
| Spec integrity | A missing or hash-mismatched spec is rejected |
| Backwards compatibility | A run without `--profile` behaves as before |
| Reproducibility | Frozen specs and their hashes are unchanged |
| Deterministic hashes | Reordered or reformatted equivalent profiles hash alike |
| Evidence invalidation | Changing a lane map voids direction evidence and not replay evidence; moving a lane voids both |
| Unverified direction | The dashboard shows the notice, and absent reads as false |
| Verified direction | Verified only when its evidence matches the active configuration |
| Fresh clone | A clean checkout holds the profiles, and missing weights or footage are named by the preflight |
| Preflight | Missing configuration is reported as missing, never as a pass |
| Security | No URL, credential, footage or frame reaches a profile, a report or a log |
| Migration | Existing commands and MQTT consumers keep working, with `SCHEMA_VERSION` unchanged |
| One implementation | Edge, preflight and demo tools share one loader |

## Consequences

**Good.** A clean clone can name what it lacks. Adding a camera has a path. Evidence cannot outlive
what it was measured on. Weaknesses travel with the camera.

**Bad.** Another file format to maintain, and a heartbeat field. Accepted: the alternative is
configuration that lives on one machine and a map nobody can check.

**Not established.** This does not make STMS universal. All evidence is three cameras on one road
network, the `domain` claim stays red, and nothing here says anything about forecast quality
(S67) or a real stream's timing (S65). Many-to-one lanes stay out: both forecasters were fitted
one lane per approach.
