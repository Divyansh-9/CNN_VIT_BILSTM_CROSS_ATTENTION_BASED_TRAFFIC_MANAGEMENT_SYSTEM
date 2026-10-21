# D3 — a committed edge program for the deployed path

**Status: implemented 2026-10-21**, after the owner's go-ahead: `edge/run.py`,
with `tests/test_edge_run.py` (PRD-CHANGELOG, D3). Where each criterion is
met is in the table at the end.

**Still owed before the TIM or SOP:** the documented start-up, verified on a
clean environment.

## The gap

Before D3, no module in `edge/` had an entry point, although `edge/node.py`'s
docstring advertised `python -m edge.node --source clip.mp4 --lanes …`. The deployed
path is:

```
detector → counting → persistence + ridge → publish → fallback
```

It had only ever run inside the Phase C harness, which is held outside the
repository with the review evidence ([HLD §9-C1](../02-design/HLD.md)).

## Done means (from the HLD review)

Moving the harness loop is not enough. D3 is done when a committed program,
for example `edge/run.py`, preserves the Phase C behaviour **and** has tests
for each of the following:

1. **Start-up arguments:** `--source`, `--lanes`, the intersection id, broker
   host and port. Missing or invalid arguments are refused at start-up; for
   the id, this is the P142 rule.
2. **The two count representations** (SAD §4.3):
   - the forecasters receive the raw lane totals, bicycles included;
   - `vehicle_count` receives the mapped breakdown (D1);
   - neither is substituted for the other.
3. **Window warm-up and reset:**
   - no class forecast before 30 contiguous samples, and no count forecast
     before 60;
   - a gap resets the window;
   - a missing lane is refused, not read as zero.
4. **Publishing and acknowledgement:** forecasts and counts published on the
   contract topics, with QoS from the topic. `last_ack` advances only on a
   successful publish.
5. **Local fallback and recovery, measured from `last_ack`:**
   - `LOCAL` once more than 10 s have passed since the last successful
     publish;
   - `NORMAL` again after a successful publish.

   Phase C measured from the broker kill instead, which is a different
   quantity (HLD §4.3).
6. **Frames:** frames stay in memory only (NFR-13), and nothing is written to
   disk.

**Not required:** the harness's failure-injection checks (F1 to F4) do not
become runtime behaviour. The safety-relevant behaviour they validated must
remain testable, which points 3 to 5 cover.

## Order

D3 comes after the batch is integrated. The batch changes `EdgeNode` (D1,
P142), and D3 builds on that. The TIM and SOP wait for D3.

## Done: where each criterion is met

| # | Criterion | Tests in `tests/test_edge_run.py` | Live run (Phase C footage, real broker) |
|---|---|---|---|
| 1 | Start-up arguments | valid settings; each required flag missing; ids outside the P142 pattern; invalid ports; approach mappings that miss, add or repeat a lane; unreviewed lanes; a camera without matching thresholds; missing files; `--source camera` without `STMS_CAMERA_URL`, and the URL never echoed | started from the command line, exit 0 |
| 2 | Two count representations | raw totals (bicycle included) reach both forecasters; the wire gets the mapped breakdown, bicycle dropped; the calibrated confidence applies to both | 224 bicycle detections excluded from the wire only, the same 224 as Phase C |
| 3 | Warm-up and reset | no class forecast before 30 samples, no count forecast before 60; a gap resets both; a missing lane is refused, nothing filled in, and the hole restarts the window | — |
| 4 | Publishing and acknowledgement | every publish on its contract topic at that topic's QoS; `last_ack` advances only on success | 271 class and 241 count forecasts stored, identical payload for payload to Phase C (timestamps aside) |
| 5 | Fallback from `last_ack` | LOCAL at 12 s after the last ack, which is only 10 s after the drop, so a drop-timed rule would still say NORMAL; recovery on the next success; the local cycle alternates; still decided while the camera reconnects | broker killed: LOCAL logged 12.0 s after the last successful publish; NORMAL 1.0 s after the broker restarted |
| 6 | Frames in memory only | each frame is released before the next arrives; no file opened for writing; nothing new on disk | no new file in the snapshot besides the server's own store |

Twelve mutants, each reverting one protection in `edge/run.py`, were all
caught by these tests.
