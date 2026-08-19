"""Week-2 pilot analysis (Execution Manual §1.2, PLAN-01 WI-02).

Two questions, answered from one count series, before any corpus is built:

1. **Are the §14.1 thresholds usable on real traffic?** If counts above 15 never
   occur, HIGH is degenerate, macro F1 ≥ 0.80 is unreachable, and the thresholds
   need recalibrating (pending item P1).

2. **Does the task require prediction at all?** If the class at t+60s almost
   always equals the class now, a last-value baseline sits near the ceiling and
   **no model can be ranked against another** (PRD A17). A corpus can be
   perfectly balanced and still unable to separate any two methods.

The second question can invalidate the whole task design, and it costs the same
detector run as the first.

Pure arithmetic over a count series, so it is testable before a detector exists.
The video and YOLO wiring lives in `scripts/pilot_counts.py`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Mapping, Sequence

from .labels import CongestionClass, label_from_count, smooth_counts
from .windows import WindowGeometry

__all__ = ["PilotResult", "analyse_counts"]


@dataclass(frozen=True)
class PilotResult:
    frames: int
    windows: int
    class_counts: Mapping[str, int]
    class_shares: Mapping[str, float]
    transition_rate: float
    naive_accuracy: float
    count_percentiles: Mapping[int, int]
    max_count: int

    @property
    def thresholds_usable(self) -> bool:
        return all(s >= 0.05 for s in self.class_shares.values())

    # The rule this gate implements, stated in BUILD-LOG S06: "if ~90% of
    # windows do not change class within 60 seconds, a last-value baseline sits
    # near the ceiling and no model can be ranked against another."
    #
    # 90% unchanged is a 10% transition rate. The gate was written at 0.05, so
    # it passed the exact condition it was created to catch — measured: the COCO
    # arm of the Dhaka pilot reported a **93.1% naive baseline** and printed
    # PASS. A gate that admits the failure it names is not a gate.
    #
    # **This change is adverse to us and was made knowing that.** It is a
    # tightening, not a relaxation, and it flips a result we had already
    # recorded as passing. The reported arm (our detector, 31.0%) passes either
    # way, so nothing here was moved to rescue a number — the opposite.
    MIN_TRANSITION_RATE = 0.10

    @property
    def task_is_learnable(self) -> bool:
        return self.transition_rate >= self.MIN_TRANSITION_RATE

    def report(self) -> str:
        lines = [
            f"frames analysed      {self.frames}",
            f"prediction windows   {self.windows}",
            "",
            "class distribution at the label frame:",
        ]
        for name, share in self.class_shares.items():
            bar = "#" * int(share * 40)
            flag = "  <-- BELOW 5%" if share < 0.05 else ""
            lines.append(f"  {name:<7} {self.class_counts[name]:>6}  {share:>6.1%} {bar}{flag}")

        lines += [
            "",
            f"count percentiles    "
            + "  ".join(f"p{p}={v}" for p, v in self.count_percentiles.items()),
            f"maximum count        {self.max_count}",
            "",
            f"transition rate      {self.transition_rate:.1%}  "
            f"(windows where the class CHANGES over the horizon)",
            f"naive baseline       {self.naive_accuracy:.1%}  "
            f"(accuracy of predicting 'same as now')",
            "",
        ]

        if not self.thresholds_usable:
            rare = [n for n, s in self.class_shares.items() if s < 0.05]
            lines += [
                f"VERDICT 1  FAIL — {', '.join(rare)} below 5%.",
                "  The §14.1 thresholds do not fit this traffic. Recalibrate them",
                "  (pending item P1) BEFORE building a corpus. Use the percentiles",
                "  above: thresholds near p33 and p67 give a balanced three-way split.",
            ]
        else:
            lines.append("VERDICT 1  PASS — all three classes occur often enough to learn.")

        lines.append("")
        if not self.task_is_learnable:
            lines += [
                f"VERDICT 2  FAIL — only {self.transition_rate:.1%} of windows change class.",
                f"  A model that always answers 'same as now' scores "
                f"{self.naive_accuracy:.1%}.",
                "  No model can be ranked against another on this task. Before",
                "  continuing, either lengthen the horizon beyond 60s or move the",
                "  class boundaries so transitions become common (PRD A17).",
                "  THIS IS THE FINDING THAT CHANGES THE PROJECT. Do not skip past it.",
            ]
        else:
            lines += [
                f"VERDICT 2  PASS — {self.transition_rate:.1%} of windows change class.",
                f"  The naive baseline scores {self.naive_accuracy:.1%}. That is the bar",
                "  every model must clear, and it belongs in the paper.",
            ]
        return "\n".join(lines)


def analyse_counts(
    counts: Sequence[int],
    geometry: WindowGeometry | None = None,
    *,
    smooth_window: int = 3,
    low_max: int = 4,
    med_max: int = 15,
) -> PilotResult:
    """Analyse one lane's per-frame count series.

    Args:
        counts: vehicles in the lane, one entry per sampled frame (5 s apart).
        geometry: window timing. Defaults to the PRD values.
        smooth_window: median smoothing, as the corpus builder uses.
        low_max, med_max: §14.1 thresholds. Parameters because P1 expects these
            to change once real data exists — which is what this pilot measures.
    """
    g = geometry or WindowGeometry()
    if len(counts) < g.min_frames:
        raise ValueError(
            f"need at least {g.min_frames} sampled frames "
            f"({g.min_clip_s}s of video) to form one window; got {len(counts)}"
        )

    smoothed = smooth_counts(counts, smooth_window)

    labels_at_target: list[int] = []
    labels_now: list[int] = []
    for start in range(0, len(smoothed) - g.min_frames + 1, g.stride_frames):
        last = start + g.T - 1
        target = start + g.label_offset_frames
        labels_now.append(int(label_from_count(smoothed[last], low_max=low_max, med_max=med_max)))
        labels_at_target.append(
            int(label_from_count(smoothed[target], low_max=low_max, med_max=med_max))
        )

    hist = Counter(labels_at_target)
    total = len(labels_at_target)
    names = [c.label for c in CongestionClass]

    transitions = sum(1 for a, b in zip(labels_now, labels_at_target) if a != b)
    ordered = sorted(smoothed)

    return PilotResult(
        frames=len(counts),
        windows=total,
        class_counts={n: hist.get(i, 0) for i, n in enumerate(names)},
        class_shares={n: hist.get(i, 0) / total for i, n in enumerate(names)},
        transition_rate=transitions / total if total else 0.0,
        naive_accuracy=1 - (transitions / total) if total else 0.0,
        count_percentiles={
            p: ordered[min(len(ordered) - 1, int(len(ordered) * p / 100))]
            for p in (10, 33, 50, 67, 90)
        },
        max_count=max(smoothed) if smoothed else 0,
    )
