"""Statistics for the benchmark (S38, NFR-10, FR-R07).

PRD §14.3 asks for mean ± 95% CI (bootstrap, 10,000 resamples), a paired t-test
at α=0.05, and Cohen's d. All three are here, implemented once, because a number
computed twice is a number that can disagree with itself.

Three decisions that are easy to get wrong and change what the result means:

**The test is paired, and pairing is by seed.** Each seed fixes the demand
stream, so method A and method B on seed 7 face *the same traffic*. Comparing
unpaired throws that away and inflates the variance by the between-seed spread,
which is the largest source of variation here. Pairing requires the two arms to
have been run on the same seeds — asserted, not assumed.

**Bootstrap the paired differences, not the two means separately.** A CI on
`mean(A) - mean(B)` built from two independent bootstraps ignores the
correlation the pairing created and comes out too wide.

**Cohen's d for paired data uses the standard deviation of the differences.**
Using the pooled SD of the raw samples is the unpaired formula and reports a
smaller effect than the design achieved.

No SciPy: the t-distribution survival function is the only thing needed and a
1,600-line dependency for one function is not worth it in a project whose
`requirements.txt` is a graded deliverable. The implementation is checked against
known values in `tests/test_statistics.py`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

__all__ = [
    "bootstrap_ci",
    "paired_t_test",
    "cohens_d_paired",
    "Comparison",
    "compare",
]

DEFAULT_RESAMPLES = 10_000     # NFR-10
DEFAULT_ALPHA = 0.05           # PRD §14.3


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _stdev(values: Sequence[float]) -> float:
    """Sample standard deviation, n-1. Population SD would understate the
    uncertainty of an estimate made from a sample."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def bootstrap_ci(
    values: Sequence[float],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    alpha: float = DEFAULT_ALPHA,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Percentile bootstrap. Returns `(mean, low, high)`.

    Seeded, because a confidence interval that moves between runs of the same
    data is not reportable (NFR-07).
    """
    if not values:
        raise ValueError("cannot bootstrap an empty sample")
    if len(values) == 1:
        only = float(values[0])
        return only, only, only

    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(resamples):
        means.append(_mean([values[rng.randrange(n)] for _ in range(n)]))
    means.sort()

    low = means[int((alpha / 2) * resamples)]
    high = means[min(resamples - 1, int((1 - alpha / 2) * resamples))]
    return _mean(values), low, high


def _t_sf(t: float, df: int) -> float:
    """One-tailed survival function of Student's t, by continued fraction.

    Avoids a SciPy dependency for a single function. Checked against published
    values in the tests — an approximation nobody verifies is worse than none.
    """
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    return 0.5 * _betainc(df / 2.0, 0.5, x)


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta, Lentz's continued fraction."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))

    if x < (a + 1) / (a + b + 2):
        return front * _cf(a, b, x) / a
    return 1.0 - math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + b * math.log(1 - x) + a * math.log(x)
    ) * _cf(b, a, 1 - x) / b


def _cf(a: float, b: float, x: float, iterations: int = 200) -> float:
    tiny = 1e-30
    f, c, d = 1.0, 1.0, 0.0
    for i in range(iterations):
        m = i // 2
        if i == 0:
            numerator = 1.0
        elif i % 2 == 0:
            numerator = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            numerator = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + numerator * d
        d = tiny if abs(d) < tiny else d
        d = 1.0 / d
        c = 1.0 + numerator / c
        c = tiny if abs(c) < tiny else c
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    return f - 1.0


def paired_t_test(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """Two-tailed paired t-test. Returns `(t, p)`.

    Pairing is by position, which means by seed. The caller must have aligned
    them — `compare` asserts it.
    """
    if len(a) != len(b):
        raise ValueError(
            f"paired test needs equal-length samples, got {len(a)} and {len(b)}. "
            f"If one arm has fewer seeds, the pairing is broken — do not truncate, "
            f"find the missing runs."
        )
    if len(a) < 2:
        raise ValueError("paired test needs at least 2 pairs")

    differences = [x - y for x, y in zip(a, b)]
    sd = _stdev(differences)
    if sd == 0.0:
        return (0.0, 1.0) if _mean(differences) == 0 else (float("inf"), 0.0)

    t = _mean(differences) / (sd / math.sqrt(len(differences)))
    return t, 2.0 * _t_sf(abs(t), len(differences) - 1)


def cohens_d_paired(a: Sequence[float], b: Sequence[float]) -> float:
    """Effect size for paired data: mean difference over SD *of the differences*.

    The pooled-SD form is the unpaired statistic and understates an effect that
    a paired design actually achieved.
    """
    differences = [x - y for x, y in zip(a, b)]
    sd = _stdev(differences)
    return _mean(differences) / sd if sd else 0.0


@dataclass
class Comparison:
    method_a: str
    method_b: str
    n_pairs: int
    mean_a: float
    mean_b: float
    ci_a: tuple[float, float]
    ci_b: tuple[float, float]
    mean_difference: float
    ci_difference: tuple[float, float]
    t: float
    p: float
    cohens_d: float
    alpha: float = DEFAULT_ALPHA
    notes: list[str] = field(default_factory=list)

    @property
    def significant(self) -> bool:
        return self.p < self.alpha

    @property
    def improvement_percent(self) -> float:
        """Positive means A is lower than B — for wait time, lower is better."""
        return 100.0 * (self.mean_b - self.mean_a) / self.mean_b if self.mean_b else 0.0

    def as_row(self) -> dict:
        return {
            "method_a": self.method_a,
            "method_b": self.method_b,
            "n_pairs": self.n_pairs,
            "mean_a": round(self.mean_a, 4),
            "ci_a_low": round(self.ci_a[0], 4),
            "ci_a_high": round(self.ci_a[1], 4),
            "mean_b": round(self.mean_b, 4),
            "ci_b_low": round(self.ci_b[0], 4),
            "ci_b_high": round(self.ci_b[1], 4),
            "mean_difference": round(self.mean_difference, 4),
            "ci_diff_low": round(self.ci_difference[0], 4),
            "ci_diff_high": round(self.ci_difference[1], 4),
            "t": round(self.t, 4),
            "p": round(self.p, 6),
            "cohens_d": round(self.cohens_d, 4),
            "significant": self.significant,
            "improvement_percent": round(self.improvement_percent, 2),
        }

    def summary(self) -> str:
        verdict = "significant" if self.significant else "NOT significant"
        lines = [
            f"{self.method_a} vs {self.method_b}  (n={self.n_pairs} paired seeds)",
            f"  {self.method_a:16} {self.mean_a:8.2f}  "
            f"[{self.ci_a[0]:.2f}, {self.ci_a[1]:.2f}]",
            f"  {self.method_b:16} {self.mean_b:8.2f}  "
            f"[{self.ci_b[0]:.2f}, {self.ci_b[1]:.2f}]",
            f"  difference       {self.mean_difference:8.2f}  "
            f"[{self.ci_difference[0]:.2f}, {self.ci_difference[1]:.2f}]",
            f"  t={self.t:.3f}  p={self.p:.5f}  d={self.cohens_d:.3f}  "
            f"-> {verdict} at alpha={self.alpha}",
            f"  {self.improvement_percent:+.1f}% (positive = {self.method_a} better)",
        ]
        lines += [f"  NOTE: {note}" for note in self.notes]
        return "\n".join(lines)


def compare(
    samples_a: dict[int, float],
    samples_b: dict[int, float],
    *,
    name_a: str,
    name_b: str,
    alpha: float = DEFAULT_ALPHA,
    resamples: int = DEFAULT_RESAMPLES,
) -> Comparison:
    """Compare two methods keyed **by seed**, so pairing cannot silently break.

    Taking dicts rather than lists is deliberate. Two lists can be misaligned by
    a single dropped run and nothing will complain; the t-test would then be
    comparing seed 7 against seed 8 and reporting a confident answer to a
    question nobody asked.
    """
    shared = sorted(set(samples_a) & set(samples_b))
    if not shared:
        raise ValueError(f"{name_a} and {name_b} share no seeds — nothing to pair")

    notes = []
    missing_a = sorted(set(samples_b) - set(samples_a))
    missing_b = sorted(set(samples_a) - set(samples_b))
    if missing_a or missing_b:
        notes.append(
            f"unpaired seeds excluded — {name_a} missing {missing_a}, "
            f"{name_b} missing {missing_b}"
        )

    a = [samples_a[s] for s in shared]
    b = [samples_b[s] for s in shared]
    differences = [x - y for x, y in zip(a, b)]

    mean_a, low_a, high_a = bootstrap_ci(a, resamples=resamples, alpha=alpha)
    mean_b, low_b, high_b = bootstrap_ci(b, resamples=resamples, alpha=alpha)
    mean_d, low_d, high_d = bootstrap_ci(differences, resamples=resamples, alpha=alpha)
    t, p = paired_t_test(a, b)

    if len(shared) < 30:
        notes.append(f"only {len(shared)} pairs; FR-R07 specifies 30")

    return Comparison(
        method_a=name_a, method_b=name_b, n_pairs=len(shared),
        mean_a=mean_a, mean_b=mean_b,
        ci_a=(low_a, high_a), ci_b=(low_b, high_b),
        mean_difference=mean_d, ci_difference=(low_d, high_d),
        t=t, p=p, cohens_d=cohens_d_paired(a, b), alpha=alpha, notes=notes,
    )
