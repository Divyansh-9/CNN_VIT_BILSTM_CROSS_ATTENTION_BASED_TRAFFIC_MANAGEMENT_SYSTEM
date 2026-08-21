"""The reproduction check must refuse before the discordance is computed (P59).

Predictions may come from runs made after the metrics table was published. If
seeding or determinism drifted, Q1 and Q2 would describe different models and
the discordance count would not be about the published table.

So the ordering is the property under test: verification first, refusal on any
mismatch, and no output at all when it fails. A discordance count from
unverified predictions is worse than none, because it looks like evidence.
"""

from __future__ import annotations

import csv

from scripts.discordance import (
    load_metrics,
    load_predictions,
    mcnemar,
    verify_reproduction,
)

CLASSES = ("LOW", "MEDIUM", "HIGH")


def write_pair(tmp_path, config="G", fold="0", seed="42",
               true=("LOW", "MEDIUM", "HIGH", "LOW"),
               pred=("LOW", "MEDIUM", "HIGH", "LOW"),
               macro_f1=None, accuracy=None, qwk=None):
    """A predictions file and the metrics row that should describe it."""
    from mfstnet.metrics import evaluate

    report = evaluate([CLASSES.index(t) for t in true],
                      [CLASSES.index(p) for p in pred], CLASSES)
    records = [{"config": config, "seed": seed, "fold": fold,
                "clip_id": "clip", "start_index": i, "label_index": i + 89,
                "lane": f"lane_{i}", "true": t, "pred": p,
                "correct": int(t == p)}
               for i, (t, p) in enumerate(zip(true, pred))]
    path = tmp_path / f"fold{fold}_seed{seed}_{config}.predictions.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    row = {"config": config, "fold": fold, "seed": seed,
           "macro_f1": round(macro_f1 if macro_f1 is not None
                             else report.macro_f1, 4),
           "accuracy": round(accuracy if accuracy is not None
                             else report.accuracy, 4),
           "qwk": round(qwk if qwk is not None else report.qwk, 4)}
    metrics_path = tmp_path / f"fold{fold}_seed{seed}_{config}.csv"
    with metrics_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return path


def test_matching_predictions_and_metrics_verify(tmp_path):
    write_pair(tmp_path)
    problems = verify_reproduction("G", load_predictions(tmp_path, "G"),
                                   load_metrics(tmp_path, "G"))
    assert problems == []


def test_drifted_metrics_are_refused(tmp_path):
    """The case the guard exists for: the model was re-run and came out
    different, so the predictions are not the published table's model."""
    write_pair(tmp_path, macro_f1=0.1234)
    problems = verify_reproduction("G", load_predictions(tmp_path, "G"),
                                   load_metrics(tmp_path, "G"))
    assert problems
    assert "not the model the table describes" in problems[0]


def test_predictions_with_no_committed_row_are_refused(tmp_path):
    path = write_pair(tmp_path)
    (tmp_path / "fold0_seed42_G.csv").unlink()
    assert path.exists()
    problems = verify_reproduction("G", load_predictions(tmp_path, "G"),
                                   load_metrics(tmp_path, "G"))
    assert problems and "no committed metrics row" in problems[0]


def test_committed_runs_without_predictions_are_refused(tmp_path):
    """Otherwise the discordance covers a different set of runs than the table
    and nothing says so."""
    write_pair(tmp_path, fold="0")
    write_pair(tmp_path, fold="1")
    (tmp_path / "fold1_seed42_G.predictions.csv").unlink()
    problems = verify_reproduction("G", load_predictions(tmp_path, "G"),
                                   load_metrics(tmp_path, "G"))
    assert problems and "no predictions file" in problems[0]


def test_the_cli_refuses_and_writes_nothing_when_verification_fails(tmp_path):
    from scripts.discordance import main

    write_pair(tmp_path, config="G", macro_f1=0.1234)
    write_pair(tmp_path, config="H")
    out = tmp_path / "discordance.csv"
    assert main(["--dir", str(tmp_path), "--out", str(out)]) == 1
    assert not out.exists(), "a failed check must not leave a result behind"


def test_the_cli_computes_when_verification_passes(tmp_path):
    from scripts.discordance import main

    write_pair(tmp_path, config="G",
               true=("LOW", "MEDIUM", "HIGH", "LOW"),
               pred=("LOW", "MEDIUM", "HIGH", "LOW"))
    write_pair(tmp_path, config="H",
               true=("LOW", "MEDIUM", "HIGH", "LOW"),
               pred=("LOW", "MEDIUM", "LOW", "LOW"))
    out = tmp_path / "discordance.csv"
    assert main(["--dir", str(tmp_path), "--out", str(out)]) == 0
    row = list(csv.DictReader(out.open(encoding="utf-8")))[0]
    assert int(row["different_predictions"]) == 1
    assert int(row["G_right_H_wrong"]) == 1


# --------------------------------------------------------------- McNemar --


def test_no_discordant_pairs_gives_p_of_one():
    assert mcnemar(0, 0) == 1.0


def test_symmetric_discordance_is_not_significant():
    assert mcnemar(5, 5) > 0.9


def test_one_sided_discordance_is_significant():
    assert mcnemar(10, 0) < 0.01


def test_p_never_exceeds_one():
    """Doubling a one-tailed probability can overshoot without the clamp."""
    assert all(mcnemar(a, b) <= 1.0
               for a in range(6) for b in range(6))


def test_the_column_name_carries_the_violated_assumption(tmp_path):
    """A p-value whose assumption is broken must not be reachable under a name
    that reads as ordinary."""
    from scripts.discordance import main

    write_pair(tmp_path, config="G")
    write_pair(tmp_path, config="H")
    out = tmp_path / "discordance.csv"
    main(["--dir", str(tmp_path), "--out", str(out)])
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert "INDEPENDENCE_VIOLATED" in header


def test_a_difference_exactly_at_the_tolerance_is_allowed(tmp_path):
    """Deliberate. The committed CSVs round to four decimals, so a re-score
    differing by exactly one unit in the last place is rounding, not drift —
    and a guard that fired on it would fail on every honest reproduction."""
    write_pair(tmp_path, macro_f1=0.9999)      # against a true 1.0
    assert verify_reproduction("G", load_predictions(tmp_path, "G"),
                               load_metrics(tmp_path, "G")) == []
