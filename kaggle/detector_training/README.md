# Kaggle S11 — how to actually run this

Six failed versions taught this workflow. It is written down because none of it
is discoverable from the Kaggle API docs.

## The commands

```bash
python scripts/kaggle_push.py --check      # credentials + staged files
python scripts/kaggle_push.py --dataset    # 0.98 GB, once per data change
python scripts/kaggle_push.py --kernel     # code only
```

Then **run it from the web UI**, not from the CLI. See below for why.

## Three Kaggle behaviours that cost six versions

### 1. `kernels push` always resets the accelerator to P100

There is a `machine_shape` field in kernel metadata and it does **not** carry the
GPU type — it round-trips as the generic string `"Gpu"`. Inspecting the browser's
own network traffic while changing the dropdown shows Kaggle sending
`"accelerator":"GPU"` both before and after, so the P100-versus-T4 choice is a
**session** setting the kernel API cannot express.

The CLI's `--accelerator` flag accepts any string, including
`INVALID_PROBE`, without complaint or effect.

**So: push code with the API, then set T4 and Save & Run All in the UI.**

### 2. The P100 cannot run current PyTorch at all

Kaggle's P100 is compute capability **sm_60**. The installed PyTorch supports
sm_70 and above. This surfaces only as a `UserWarning` that scrolls past while
the run continues — it does not stop anything, and the run dies later somewhere
confusing.

The notebook's second cell now **fails immediately** on an unsupported
capability, which turns an hour of wasted quota into fifteen seconds.

Use **GPU T4 x2** (sm_75). It is also 2 GPUs against 1.

### 3. A dataset does not mount where its slug suggests

The mount slug is `datasets/idredk/indiatrafficnet-bootstrap-idd-yolo`, so
`/kaggle/input` contains a single `datasets` directory and the data sits **three
levels down** — not at `/kaggle/input/<dataset-name>`.

Two versions died asserting the flat path, and the assertion reported only that
it was missing, never what was actually there. The notebook now **prints the
mount and searches for the YOLO layout**, so any future slug change is a
non-event.

## Reading the output

`s11_detector_metrics.csv` is the deliverable. Download it and commit it to
`experiments/results/` — the paper's table is generated from that file, never
retyped (NFR-09/10).

Per-class support sits beside every metric (FR-D08). `cattle` is the thinnest
class at roughly 1,162 training boxes, and `e_rickshaw` is **0 by design** —
no public dataset assessed carries it, which is pending item **P12**.

The fps figure is a **proxy**. ADR-003 made the edge node a laptop, and a T4 is
not it, so that number bounds FR-D06 rather than demonstrating it.

---

## 4. `kernels push` cannot set the GPU **type**, and a new notebook defaults to P100

Learned twice, which is once too many.

`kernel-metadata.json` carries `"enable_gpu": true` and `"machine_shape": "Gpu"`.
Neither selects *which* GPU. The accelerator is a per-notebook **session setting**
that only the editor UI can change, and **every new notebook starts on GPU P100**
regardless of what any earlier notebook was set to.

Kaggle's P100 is compute capability **sm_60**. Current PyTorch builds start at
sm_70, so the card is **unusable, not merely slow** — and the only signal is a
`UserWarning` that scrolls past while the run continues to its eventual failure.

S14 version 1 hit this. The hard gate in cell 1 caught it in **14.4 seconds**:

```
arch   sm_60 | build supports ['sm_70', 'sm_75', ...]
SystemExit: INCOMPATIBLE GPU sm_60; ... Settings -> Accelerator -> GPU T4 x2 (sm_75).
```

That gate is the reason this cost seconds rather than an hour of a 30-hour weekly
quota. **Keep it in every notebook.**

### The fix, in order

1. Open the notebook editor.
2. Right panel → **Session options** → **Accelerator** → **GPU T4 x2**, and
   confirm the "Turn on GPU T4 x2" dialog.
3. Check the **Input** panel lists `IndiaTrafficNet Bootstrap - IDD YOLO 8class`.
   `dataset_sources` in `kernel-metadata.json` does carry across a push, but a
   UI *Save & Run All* uses whatever the **draft** has attached.
4. **Save Version** → type **Save & Run All (Commit)** → Save.

### Confirm it from the command line rather than the tab

```
python -m kaggle kernels status idredk/cnn-vit-bilstm-cross-attention-traffic-system-s14
```

`KernelWorkerStatus.RUNNING` means it is genuinely queued and running, which the
editor does not always make obvious.

---

## 5. **`kernels push` RESETS the accelerator to P100.** Always set it after pushing

This is the one that makes the API path incomplete, and it is worth stating
bluntly because behaviour 4 alone implies the wrong workflow.

Setting **GPU T4 x2** in the editor is not sticky across a push. S14 version 2
ran on T4 x2 after the setting was made by hand. Version 3 was then pushed with
`kernels push` — no metadata change touching the GPU — and **ran on P100 again**,
dying in 14.7 s on the sm_60 gate.

So `kernel-metadata.json` is authoritative for code, inputs and privacy, and the
accelerator is **session state the push overwrites with the default**.

### The workflow that actually works

```
python scripts/kaggle_push.py --kernel --dir kaggle/joint_training
```

then, **every time, in the editor**:

1. Session options → Accelerator → **GPU T4 x2** → confirm the dialog
2. Check the Input panel still lists the dataset
3. **Save Version** → **Save & Run All (Commit)** → Save
4. `python -m kaggle kernels status <id>` → expect `RUNNING`

**Never push and walk away.** A pushed version starts running immediately, on
P100, and fails — burning a version number and, without the gate, potentially an
hour of quota.

### Cost so far, and why the gate earns its place

| version | accelerator | outcome |
|---|---|---|
| 1 | P100 (default) | gate fired at **14.4 s** |
| 2 | T4 x2 (set by hand) | trained 2.6 h, failed on a data defect the gate could not see |
| 3 | P100 (**push reset it**) | gate fired at **14.7 s** |
| 4 | T4 x2 (set by hand again) | running |

Two of four versions died to this single behaviour, and both cost seconds
because cell 1 checks `torch.cuda.get_device_capability` against
`torch.cuda.get_arch_list()`. Without it, both would have been hour-scale
failures against a 30-hour weekly quota.
