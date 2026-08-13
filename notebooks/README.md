# Notebooks — what belongs here, and what does not

Notebooks are a **presentation and driver layer** in this project. They read from
the library in `mfstnet/` and from committed result CSVs; they do not contain
model code, training loops, or any number that another file also holds.

This is not stylistic fussiness. Two project rules force it:

- **NFR-09/10** — result CSVs are written by the script that produced them and
  never transcribed. Paper tables are generated from committed CSVs by a
  committed script. A metric computed inside a notebook and typed into a report
  is exactly the transcription this forbids.
- **NFR-15/16** — the eight-config ablation must run from config alone, with no
  code edit between configs. Configs A–H at five seeds each is **40 runs**. That
  is a command-line loop, not forty rounds of clicking Run All.

## Honest note on version history

Notebooks are the *worst* common format for git history, which is worth saying
plainly because it is the usual reason people reach for them.

A `.ipynb` is JSON with execution counts, cell IDs and base64-encoded output
images embedded in it. Re-running a notebook without changing a line of code
still produces a large diff. Two people editing one notebook produce a merge
conflict inside a JSON blob that neither can read. Git *stores* the history
faithfully; nobody can *review* it.

So version history is a reason to keep the load-bearing code in `.py`, not a
reason to move it into notebooks. What notebooks genuinely give is inline
figures, narrative beside output, and Colab — and this directory is scoped to
exactly those.

## The split

| Belongs in `.py` | Belongs in a notebook |
|---|---|
| Model, fusion, temporal, cache | Looking at footage and drawing lane polygons |
| Training loop and ablation harness | Rendering committed result CSVs as tables and figures |
| Metric *computation* (`mfstnet/metrics.py`) | Metric *presentation* — confusion matrices, F1 bars |
| Anything CI runs | The Colab driver, because Colab is notebook-only |
| Anything imported by something else | One-off exploration that will not be re-run |

The rule in one line: **if it needs to run 40 times, or in CI, or be imported, it
is not a notebook.**

## The notebooks

| Notebook | Status | Purpose |
|---|---|---|
| `01_explore_footage.ipynb` | blocked on S06 footage | Frame sampling, lane polygon drawing, count distribution, the A17 transition-rate check |
| `02_colab_train.ipynb` | after S28 | Thin Colab driver: install, clone, mount, invoke `scripts/train_mfstnet.py`. No model code |
| `03_results.ipynb` | **working now** | Reads `experiments/results/*.csv` and renders confusion matrices, per-class P/R/F1, ablation tables, gate analysis |
| `04_rl_benchmark.ipynb` | after S38 | 30-seed PPO vs Webster vs fixed-time, with bootstrap CIs |

## Keeping the diffs reviewable

Outputs are stripped before commit for driver notebooks. The exception is
`03_results.ipynb`, whose outputs *are* the deliverable — but every figure in it
is reproducible by re-running against the committed CSVs, so a reviewer can
check any number without trusting the stored output.

```bash
pip install nbstripout
nbstripout --install          # once per clone; strips outputs on commit
```

To run a notebook headlessly, the same way CI would:

```bash
python scripts/run_notebook.py notebooks/03_results.ipynb
python scripts/run_notebook.py notebooks/03_results.ipynb --check   # CI form
```

## Setup

```bash
pip install nbformat nbclient ipykernel pandas matplotlib
```

VS Code opens `.ipynb` natively and needs only `ipykernel`. Select the project's
`.venv` as the kernel, or imports of `mfstnet` will fail.
