"""Classification metrics for per-lane congestion prediction (PRD §14.5).

One module, used everywhere: training logs, the ablation CSV, the dashboard
benchmark page, and the paper's tables. NFR-09/10 requires paper tables to be
generated from committed CSVs by a committed script — that only holds if there
is exactly one implementation of every metric.

Pure standard library. No numpy, no scikit-learn. That keeps it runnable before
the environment exists, and makes the arithmetic auditable line by line.

Two things here are not in a default classification report, and both matter for
this task:

**The confusion matrix is a required artifact, not a diagnostic.** ADR-009 builds
the PPO training surrogate by corrupting an oracle with MFSTNet's *measured*
confusion matrix. Without it there is no surrogate and claim C4 cannot be tested.

**The classes are ordered.** LOW < MEDIUM < HIGH. Standard multiclass F1 treats
predicting HIGH when the truth is LOW exactly the same as predicting MEDIUM —
but operationally one is a wrong nudge and the other is a signal held green on an
empty road while a queue builds elsewhere. `ordinal_mae`, `off_by_two_rate` and
`quadratic_weighted_kappa` all account for the distance; plain F1 does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

__all__ = [
    "confusion_matrix",
    "ClassMetrics",
    "Report",
    "evaluate",
    "accuracy",
    "ordinal_mae",
    "off_by_two_rate",
    "quadratic_weighted_kappa",
    "format_confusion_matrix",
]

DEFAULT_LABELS = ("LOW", "MEDIUM", "HIGH")


def confusion_matrix(
    y_true: Sequence[int], y_pred: Sequence[int], n_classes: int = 3
) -> list[list[int]]:
    """Rows are truth, columns are prediction: `cm[t][p]`.

    Row/column order is fixed by this convention and depended on elsewhere —
    ADR-009 reads row `t` as "what the model predicts when the truth is t".
    """
    if len(y_true) != len(y_pred):
        raise ValueError(f"length mismatch: {len(y_true)} truths, {len(y_pred)} predictions")
    if not y_true:
        raise ValueError("no samples")

    cm = [[0] * n_classes for _ in range(n_classes)]
    for t, p in zip(y_true, y_pred):
        if not (0 <= t < n_classes and 0 <= p < n_classes):
            raise ValueError(f"label out of range for {n_classes} classes: true={t}, pred={p}")
        cm[t][p] += 1
    return cm


@dataclass(frozen=True)
class ClassMetrics:
    """Per-class figures. `support` is never optional — see Report.warnings."""

    label: str
    precision: float
    recall: float
    f1: float
    support: int


@dataclass
class Report:
    confusion: list[list[int]]
    per_class: list[ClassMetrics]
    accuracy: float
    macro_f1: float
    weighted_f1: float
    ordinal_mae: float
    off_by_two_rate: float
    qwk: float
    n: int
    labels: tuple[str, ...] = DEFAULT_LABELS
    warnings: list[str] = field(default_factory=list)

    def as_row(self) -> dict[str, float | int | str]:
        """Flat dict for a CSV row. Result CSVs are written by the script that
        produced them, never transcribed (NFR-09)."""
        row: dict[str, float | int | str] = {
            "n": self.n,
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "weighted_f1": round(self.weighted_f1, 4),
            "ordinal_mae": round(self.ordinal_mae, 4),
            "off_by_two_rate": round(self.off_by_two_rate, 4),
            "qwk": round(self.qwk, 4),
        }
        for m in self.per_class:
            key = m.label.lower()
            row[f"precision_{key}"] = round(m.precision, 4)
            row[f"recall_{key}"] = round(m.recall, 4)
            row[f"f1_{key}"] = round(m.f1, 4)
            row[f"support_{key}"] = m.support
        for t, label in enumerate(self.labels):
            for p, pred_label in enumerate(self.labels):
                row[f"cm_{label.lower()}_as_{pred_label.lower()}"] = self.confusion[t][p]
        return row


def accuracy(cm: list[list[int]]) -> float:
    total = sum(sum(r) for r in cm)
    return sum(cm[i][i] for i in range(len(cm))) / total if total else 0.0


def ordinal_mae(cm: list[list[int]]) -> float:
    """Mean error measured in class steps.

    Predicting HIGH when the truth is LOW costs 2; predicting MEDIUM costs 1.
    Plain accuracy and F1 score both of those identically as "wrong".
    """
    total = sum(sum(r) for r in cm)
    if not total:
        return 0.0
    return sum(abs(t - p) * cm[t][p] for t in range(len(cm)) for p in range(len(cm))) / total


def off_by_two_rate(cm: list[list[int]]) -> float:
    """Fraction of predictions two classes away — LOW called HIGH, or the reverse.

    The operationally dangerous error, and worth reporting on its own because it
    is the one a traffic engineer will ask about.
    """
    total = sum(sum(r) for r in cm)
    if not total:
        return 0.0
    k = len(cm) - 1
    return (cm[0][k] + cm[k][0]) / total


def quadratic_weighted_kappa(cm: list[list[int]]) -> float:
    """Agreement beyond chance, penalising distant errors quadratically.

    The standard measure for ordered categories. 1.0 is perfect, 0.0 is chance,
    negative is worse than chance. Reported alongside macro F1 because F1 is
    blind to the ordering.
    """
    n = len(cm)
    total = sum(sum(r) for r in cm)
    if not total:
        return 0.0

    row_sum = [sum(cm[i]) for i in range(n)]
    col_sum = [sum(cm[i][j] for i in range(n)) for j in range(n)]
    denom_scale = (n - 1) ** 2

    num = den = 0.0
    for i in range(n):
        for j in range(n):
            w = ((i - j) ** 2) / denom_scale
            num += w * cm[i][j]
            den += w * (row_sum[i] * col_sum[j] / total)
    return 1.0 - num / den if den else 0.0


def evaluate(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    labels: Sequence[str] = DEFAULT_LABELS,
) -> Report:
    """Full report. Use this rather than computing anything by hand."""
    n_classes = len(labels)
    cm = confusion_matrix(y_true, y_pred, n_classes)
    total = sum(sum(r) for r in cm)

    per_class: list[ClassMetrics] = []
    warnings: list[str] = []

    for c in range(n_classes):
        tp = cm[c][c]
        fp = sum(cm[t][c] for t in range(n_classes)) - tp
        fn = sum(cm[c]) - tp
        support = sum(cm[c])

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

        per_class.append(ClassMetrics(labels[c], precision, recall, f1, support))

        # Support is reported next to every metric for the same reason FR-D08
        # requires it for detection: a class with a handful of samples produces a
        # figure that swings wildly and means almost nothing.
        if support == 0:
            warnings.append(
                f"{labels[c]} has NO samples — its precision/recall/F1 are 0 by "
                f"convention, and macro F1 is being dragged down by a class that "
                f"does not occur. Check the corpus distribution gate (PRD A17)."
            )
        elif support < 0.05 * total:
            warnings.append(
                f"{labels[c]} has only {support} of {total} samples "
                f"({support / total:.1%}). Below the 5% distribution gate — its "
                f"metrics are unstable and macro F1 is dominated by noise."
            )

    macro_f1 = sum(m.f1 for m in per_class) / n_classes
    weighted_f1 = (
        sum(m.f1 * m.support for m in per_class) / total if total else 0.0
    )

    return Report(
        confusion=cm,
        per_class=per_class,
        accuracy=accuracy(cm),
        macro_f1=macro_f1,
        weighted_f1=weighted_f1,
        ordinal_mae=ordinal_mae(cm),
        off_by_two_rate=off_by_two_rate(cm),
        qwk=quadratic_weighted_kappa(cm),
        n=total,
        labels=tuple(labels),
        warnings=warnings,
    )


def format_confusion_matrix(
    cm: list[list[int]], labels: Sequence[str] = DEFAULT_LABELS
) -> str:
    """Readable matrix for logs and the experiment record.

    Rows are truth, columns are prediction — the direction of an error is the
    whole point, and an aggregate F1 hides it.
    """
    width = max(max(len(l) for l in labels), 6) + 2
    pad = 5 + width
    lines = [
        " " * pad + "predicted".center(width * len(labels)),
        " " * pad + "".join(f"{l:>{width}}" for l in labels),
    ]
    for t, label in enumerate(labels):
        prefix = "true " if t == len(labels) // 2 else "     "
        cells = "".join(f"{cm[t][p]:>{width}}" for p in range(len(labels)))
        lines.append(f"{prefix}{label:<{width}}{cells}")
    return "\n".join(lines)
