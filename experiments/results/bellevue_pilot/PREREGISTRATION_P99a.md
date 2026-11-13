# P99a — pretrained-detector counting benchmark, fixed before any candidate runs

Written 2026-10-15, after P98. **No candidate detector has been run on
Bellevue footage before this was committed.** The project owner decided to pause
Phase 2 and to benchmark pretrained detectors before any fine-tuning. Nothing
is trained here, and no derived data is replaced. The ITD-xl corpora and every
result built on them stay as they are.

## The question

The question is whether a pretrained COCO YOLOv8 counts vehicles per lane on
this camera more accurately than the current detector (ITD-xl). P96 measured
ITD-xl's undercount at 14% / 27% / 41% on west, north and east. The forecaster's
labels are those counts, so this is the step where detector error enters.

## Reference set — the existing blind hand counts, unchanged

These are the 60 frames of the P95/P96 audit (`audit_frames.json`,
`audit_frames_2.json`), counted blind by hand under `AUDIT_PROTOCOL.md`
(`audit_manual.json`, `audit_manual_2.json`). Each frame is decoded from
`data/_bellevue/joined/…15-08_to_17-08.mp4` at the corpus's own forward
sampling with a stride of 60, so every candidate sees exactly the frame the
counter saw.

Counts are compared under the **four-lane** regions that were hand-counted
(nearest reviewed centre within 0.25). Re-cutting the regions would change
what the hand counts mean. **The primary metric uses west, north and east**,
the three lanes P97 kept. South is out of view (P96) and is reported only.

**Limitation, stated before the run.** All 60 frames are from the busy
afternoon, 15:08–17:08. They cannot show how any detector behaves at dawn or
in the low-sun glare of 06:08–08:08, and that is where 87% of the corpus's
LOW labels come from. This benchmark therefore **cannot adopt a detector on
its own** (see Decision).

## Harness check — must pass before any candidate counts

The reference detector is run through the benchmark harness at its pinned
settings: ITD-xl, conf 0.45, imgsz 992, its own vehicle classes. It must
reproduce `data/corpus_bellevue/counts.csv` **exactly** on all 60 frames and
all four lanes. If it does not, the harness is wrong and nothing is reported.

## Candidates — all fixed here

| id | weights | imgsz | conf | role |
|---|---|---|---|---|
| R | ITD-xl `best_xl_ITD_v1.2.pt` | 992 | 0.45 | reference (as built) |
| S640 | COCO `yolov8s.pt` | 640 | 0.25 | candidate |
| M640 | COCO `yolov8m.pt` | 640 | 0.25 | candidate |
| X640 | COCO `yolov8x.pt` | 640 | 0.25 | candidate |
| S1280 | COCO `yolov8s.pt` | 1280 | 0.25 | candidate |
| M1280 | COCO `yolov8m.pt` | 1280 | 0.25 | candidate |
| X1280 | COCO `yolov8x.pt` | 1280 | 0.25 | candidate |

- **Weights:** the official Ultralytics assets release `v8.4.0`, fetched by
  ultralytics 8.4.118 before this was committed:
  - `yolov8s.pt` `1f47a78bf100391c2a140b7ac73a1caae18c32779be7d310658112f7ac9aa78a`
  - `yolov8m.pt` `5d4a90cdc7a21786cc59cd19778e9eafff836df9e2da32524737c7ee6efe4fe5`
  - `yolov8x.pt` `3df4ada6b4dad6d657868f2fdf7faecfb34dcfccf3a25c4b82079064718524c8`
- **Device:** every detector runs exactly as `build_corpus.py` ran ITD-xl,
  with Ultralytics' default device, so that the harness check is meaningful.
- **Classes counted for COCO:** bicycle, car, motorcycle, bus and truck. This
  matches the hand-count rule. Train, boat and airplane are not counted.
- **conf 0.25** is the Ultralytics default, the setting COCO results are
  reported at. It is **not tuned** here, and no other value is tried.
- **640** is the size the COCO weights were trained at. **1280** is included
  because the north undercount concentrates in the small, distant queue.

## Primary metric and decision rule

- **Per lane:** for each frame, the absolute error |detector − hand|.
  **Primary:** the mean over frames and over west, north and east (3-lane MAE).
- **Comparison:** candidate − R on the 3-lane MAE, with a **paired bootstrap
  over frames** (10,000 resamples, seed 0). The frame is the cluster, and its
  lanes are resampled together.
- **A candidate improves on R** when the 95% interval of that difference lies
  entirely below zero.
- **Selection:** of the candidates that improve on R, the lowest point MAE is
  selected. If two are within 0.05 vehicles, the smaller model is selected,
  because the edge node runs the detector too (≥ 10 fps, PRD).

Six candidates are compared against one reference on 60 correlated frames, so
the selected candidate's margin is optimistic. That is why the decision below
requires confirmation.

## Reported regardless of outcome

Per lane and per candidate:

- MAE, signed bias, undercount percentage, exact agreement, and Pearson
  correlation;
- the quiet and busy halves, split at the hand-count median exactly as in P96;
- how often the painted bicycle symbol is reported as a bicycle;
- milliseconds per frame on **this laptop's RTX 4050**. This is a proxy host
  (ADR-003), not the edge device.

## Decision

- **No candidate improves on R:** ITD-xl stays. P99 is built on the existing
  counts, and no detector is rerun.
- **A candidate is selected:** it is **not adopted yet**. First, a blind hand
  count of new frames from the LOW-bearing hours (06:08, 07:08, 08:08 and
  Sun 19:08), under the same counting rules, is scored against both R and the
  selected candidate. That set is chosen before counting and is not used for
  selection. A detector replaces ITD-xl only if it is no worse there. Any
  replacement is a **new corpus version**, built alongside the old one; the
  old one is never overwritten.

Either way, the dawn/glare count set is needed to know whether the morning
LOW labels are real. This benchmark does not decide that.

## Not done here

No fine-tuning, no annotation for training, no threshold change, no new
footage.
