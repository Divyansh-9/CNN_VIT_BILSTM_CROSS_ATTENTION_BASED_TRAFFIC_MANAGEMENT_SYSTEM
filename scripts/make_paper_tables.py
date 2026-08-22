"""Generate the paper's result tables from the committed CSVs (BR-18, NFR-09/10).

    python scripts/make_paper_tables.py --which all
    python scripts/make_paper_tables.py --which ablation --format markdown

NFR-09 requires raw results as CSV rather than summary tables, and NFR-10
requires that the tables in the paper be *generated* from those CSVs by a
committed script rather than transcribed. Everything else in this repository
already follows that rule; the tables themselves did not exist yet, which meant
the last step before the paper was still a person retyping numbers.

**What this refuses to do is the point.** A table generator that quietly emits
an empty table when its source is missing, or a bare mean when the interval is
over four points, is worse than typing the numbers by hand -- it launders the
caveat. So:

* a missing source CSV **raises**, naming the command that produces it, instead
  of writing a table with no rows;
* the ablation caption is built from the data and always states `n_folds`,
  `n_seeds` and the effective n. An interval over four camera-folds is not an
  interval over thirty seeds and must not read like one (ADR-019);
* when the largest seed spread exceeds the closest gap between two configs, the
  caption says so. Those two rows are not separated, and a ranked table invites
  a reader to separate them anyway (P54);
* a comparison marked `a_disqualified` or `b_disqualified` in
  `benchmark_stats.csv` is rendered with its disqualification, never as a plain
  row. ADR-012 disqualified those methods for a reason and the reason travels
  with the number.

Two formats, from one set of rows: `latex` (booktabs) for the submission and
`markdown` for the build log and the review deck. They are generated from the
same records so they cannot disagree.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.console import use_utf8  # noqa: E402

use_utf8()

RESULTS = Path("experiments/results")
OUT_DIR = Path("docs/paper/tables")

# Which claims a table depends on. A table whose corpus fails its own claims
# gate cannot enter the paper whatever its numbers say, so the table is not
# rendered at all (P67).
DEPENDS_ON_CLAIMS = {
    "ablation": ("domain", "class_coverage", "camera_count"),
    "control": (),          # SUMO. No corpus claim bears on it.
}

SOURCES = {
    "ablation": (RESULTS / "loco_summary.csv",
                 "python scripts/run_loco.py --corpus data/corpus "
                 "--clips data/_corpus_clips --cache data/cache_corpus "
                 "--ablation --seeds 42 1 7 13 21"),
    "control": (RESULTS / "benchmark_stats.csv",
                "python scripts/benchmark.py --seeds 30"),
}

# What each ablation config actually is, so the table is readable without the
# PRD open. §14.4, plus H from A22.
CONFIG_LABELS = {
    "A": "CNN only",
    "B": "ViT only",
    "C": "Concat fusion",
    "D": "Cross-attn (one direction)",
    "E": "Cross-attn (bidirectional, no gate)",
    "F": "+ temporal self-attention",
    "G": "Full (gated, attention pooled)",
    "H": "Linear probe",
}


def failing_claims(table: str) -> list[dict]:
    """Asserted claims this table depends on that do not currently hold.

    The ablation's eight numbers describe a corpus with no on-target camera in
    any fold and a HIGH class of 0/20/9/1. They are a real measurement of
    something, and they are not the measurement the paper claims to report — so
    rendering them at all is how they end up pasted into a draft three weeks
    later, caption and caveats stripped.

    A caption is not enough. The table is not produced.
    """
    wanted = DEPENDS_ON_CLAIMS.get(table, ())
    if not wanted:
        return []
    try:
        import yaml

        from mfstnet.corpus.composition import CameraRegistry
        from scripts.check_claims import CLAIMS, FOLDS, fold_rows, run
    except ImportError:                                   # pragma: no cover
        return []
    if not CLAIMS.is_file():
        return []
    claims = [c for c in yaml.safe_load(CLAIMS.read_text(encoding="utf-8"))["claims"]
              if c["id"] in wanted]
    folds = fold_rows(FOLDS)
    if not folds:
        return []
    results = run(claims, CameraRegistry.load(), folds)
    return [r for r in results
            if r["status"] == "asserted" and not r["passed"]]


def read_rows(path: Path, how: str) -> list[dict]:
    if not path.is_file():
        raise SystemExit(
            f"{path} does not exist, so there is no table to generate.\n"
            f"Produce it with:\n    {how}\n"
            f"A table written from a missing source is an empty table that "
            f"looks like a result."
        )
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{path} has a header and no rows.")
    return rows


def source_digest(path: Path) -> str:
    """A digest of the CSV a table was generated from.

    A caption is a claim about a run, and it outlives the run unless something
    ties them together. This repository has already produced one caption that
    said "at saturation" over a table spanning three demand regimes; that was
    caught by reading it. The digest is what turns the next one into a
    mismatch that can be checked rather than a sentence that has to be noticed.

    Same argument as P52's observation contract and P47's checkpoint sidecar,
    applied to the last artifact in the chain.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def number(value: str, places: int = 3) -> str:
    try:
        return f"{float(value):.{places}f}"
    except (TypeError, ValueError):
        return "--"


def ablation_table(rows: list[dict]) -> tuple[list[str], list[list[str]], str]:
    header = ["Config", "Description", "Macro F1", "95\\% CI", "QWK",
              "Seed spread"]
    body = []
    for row in sorted(rows, key=lambda r: r["config"]):
        interval = (f"[{number(row['macro_f1_lo'])}, "
                    f"{number(row['macro_f1_hi'])}]"
                    if row.get("macro_f1_lo") else "--")
        body.append([
            row["config"],
            CONFIG_LABELS.get(row["config"], ""),
            number(row["macro_f1_mean"]),
            interval,
            number(row.get("qwk_mean", "")),
            number(row.get("macro_f1_seed_spread", ""), 3),
        ])

    folds = max((int(r["n_folds"]) for r in rows if r.get("n_folds")), default=0)
    seeds = max((int(r["n_seeds"]) for r in rows if r.get("n_seeds")), default=0)
    caption = (
        f"Ablation over leave-one-camera-out folds (ADR-019). "
        f"{folds} folds $\\times$ {seeds} seeds per config; each fold's test "
        f"split is one held-out camera, which is the effective $n$. The "
        f"interval is a bootstrap over folds, not over sequences."
    )

    spreads = [float(r["macro_f1_seed_spread"]) for r in rows
               if r.get("macro_f1_seed_spread")]
    means = sorted(float(r["macro_f1_mean"]) for r in rows
                   if r.get("macro_f1_mean"))
    if spreads and len(means) > 1:
        closest = min(b - a for a, b in zip(means, means[1:]))
        if max(spreads) > closest:
            caption += (
                f" The largest seed spread ({max(spreads):.3f}) exceeds the "
                f"closest gap between two configurations ({closest:.3f}); those "
                f"configurations are not separated by this experiment."
            )
    if seeds < 2:
        caption += (
            " Reported at a single seed, which ranks initialisations rather "
            "than architectures and must not be read as an ablation."
        )
    return header, body, caption


def control_table(rows: list[dict]) -> tuple[list[str], list[list[str]], str]:
    header = ["Comparison", "Regime", "$n$", "Mean A", "Mean B", "$\\Delta$",
              "$p$", "Cohen's $d$", "Status"]
    body, disqualified = [], 0
    for row in rows:
        blocked = [row["method_a"] if row.get("a_disqualified") not in ("", "False", None) else "",
                   row["method_b"] if row.get("b_disqualified") not in ("", "False", None) else ""]
        blocked = [b for b in blocked if b]
        if blocked:
            disqualified += 1
            status = "disqualified: " + ", ".join(blocked)
        elif row.get("significant") in ("True", "true", "1"):
            status = "significant"
        else:
            status = "not significant"
        body.append([
            f"{row['method_a']} vs {row['method_b']}",
            row.get("regime", ""),
            row.get("n_pairs", ""),
            number(row["mean_a"], 2),
            number(row["mean_b"], 2),
            number(row["mean_difference"], 2),
            number(row["p"], 4),
            number(row["cohens_d"], 2),
            status,
        ])
    regimes = sorted({row.get("regime", "") for row in rows} - {""})
    caption = (
        f"Signal control across {', '.join(regimes) if regimes else 'all'} "
        f"demand, paired over seeds. Paired $t$-test at $\\alpha = 0.05$ with "
        f"bootstrap intervals (10{{,}}000 resamples)."
    )
    if disqualified:
        caption += (
            f" {disqualified} comparison(s) involve a method disqualified under "
            f"ADR-012 and are reported with the disqualification attached, not "
            f"omitted."
        )
    # Rendering is not meaning. This table's central comparison — a learned
    # controller against the fixed-time baselines — does not exist yet: P52
    # leaves the surrogate arm unimplemented and ADR-021's oracle run has not
    # gone. A green table with no learned method in it reads as "control is
    # done" to anyone who does not count the rows.
    methods = {row["method_a"] for row in rows} | {row["method_b"] for row in rows}
    if not (methods & {"ppo", "mfstnet", "surrogate", "oracle", "no-forecast"}):
        caption += (
            " No learned controller appears in this table: it compares the "
            "fixed-time baselines only. The PPO arms are unimplemented "
            "(P52) and the oracle bound of ADR-021 has not been run, so the "
            "comparison this table exists for is not yet answered."
        )
    return header, body, caption


def as_latex(header, body, caption, label, provenance="") -> str:
    columns = "l" * 2 + "r" * (len(header) - 2)
    lines = [
        "% Generated by scripts/make_paper_tables.py — do not edit by hand.",
        "% NFR-10: paper tables are generated from committed CSVs.",
        f"% {provenance}" if provenance else "%",
        "\\begin{table}[t]",
        "  \\centering",
        "  \\small",
        f"  \\begin{{tabular}}{{{columns}}}",
        "    \\toprule",
        "    " + " & ".join(header) + " \\\\",
        "    \\midrule",
    ]
    # str(), because a cell can arrive as a number from a caller that did
    # not come through csv.DictReader.
    lines += ["    " + " & ".join(str(cell) for cell in record) + " \\\\"
              for record in body]
    lines += [
        "    \\bottomrule",
        "  \\end{tabular}",
        f"  \\caption{{{caption}}}",
        f"  \\label{{tab:{label}}}",
        "\\end{table}",
    ]
    return "\n".join(lines) + "\n"


def demath(text: str) -> str:
    """LaTeX markup out, plain text in. One place, so the two renderings of a
    caption cannot drift into saying different things."""
    for latex, plain in (("\\%", "%"), ("\\Delta", "delta"), ("\\times", "x"),
                         ("\\alpha", "alpha"), ("{,}", ","), ("$", "")):
        text = text.replace(latex, plain)
    return text


def as_markdown(header, body, caption, label, provenance="") -> str:
    clean = [demath(h) for h in header]
    lines = [f"<!-- Generated by scripts/make_paper_tables.py ({label}) -->",
             f"<!-- {provenance} -->" if provenance else "<!-- -->",
             "",
             "| " + " | ".join(clean) + " |",
             "|" + "|".join("---" for _ in clean) + "|"]
    lines += ["| " + " | ".join(str(cell) for cell in record) + " |"
              for record in body]
    lines += ["", demath(caption)]
    return "\n".join(lines) + "\n"


BUILDERS = {"ablation": ablation_table, "control": control_table}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--which", default="all",
                        choices=("all", "ablation", "control"))
    parser.add_argument("--format", default="both",
                        choices=("both", "latex", "markdown"))
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    wanted = list(BUILDERS) if args.which == "all" else [args.which]
    formats = (["latex", "markdown"] if args.format == "both"
               else [args.format])

    args.out.mkdir(parents=True, exist_ok=True)
    blocked = 0
    for name in wanted:
        failing = failing_claims(name)
        if failing:
            blocked += 1
            print(f"  {name:<10} NOT RENDERED — the corpus fails "
                  f"{len(failing)} asserted claim(s) this table depends on:")
            for result in failing:
                print(f"               {result['id']}: {result['detail']}")
            print(f"               A caption cannot stop these numbers being "
                  f"pasted into a draft.")
            print(f"               Fix the corpus or change the claim "
                  f"(scripts/check_claims.py).")
            continue
        path, how = SOURCES[name]
        header, body, caption = BUILDERS[name](read_rows(path, how))
        provenance = f"source: {path.as_posix()} sha256:{source_digest(path)}"
        for form in formats:
            render = as_latex if form == "latex" else as_markdown
            suffix = "tex" if form == "latex" else "md"
            target = args.out / f"{name}.{suffix}"
            target.write_text(render(header, body, caption, name, provenance),
                              encoding="utf-8")
            print(f"  {name:<10} {form:<9} {len(body):>3} row(s)  -> {target}")
        print(f"    from {path}")
    print()
    print("  Generated, not transcribed (NFR-10). Regenerate after every run;")
    print("  a table that disagrees with its CSV is the CSV that is right.")
    if blocked:
        print(f"  {blocked} table(s) withheld on a failing claim.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
