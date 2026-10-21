# D3 — a committed edge program for the deployed path (tracked, not in the batch)

**Status: tracked, by the owner's review decision. Not part of the
P140–P142 / D1–D2 batch, and not started.**

**Must be resolved before the TIM or SOP claim that the deployed edge path can
be started reproducibly from the repository.**

## The gap

No module in `edge/` has an entry point, although `edge/node.py`'s docstring
advertises `python -m edge.node --source clip.mp4 --lanes …`. The deployed
path is:

```
detector → counting → persistence + ridge → publish → fallback
```

It has only ever run inside the Phase C harness, which is held outside the
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
