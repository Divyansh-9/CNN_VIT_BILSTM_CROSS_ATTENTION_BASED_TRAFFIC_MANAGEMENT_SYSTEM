"""A generated table must carry the caveats its numbers cannot be read without.

NFR-10 says the paper's tables are generated from committed CSVs rather than
transcribed. The risk in automating that is subtler than a typo: a generator
will happily emit a clean, confident table from four data points, or from a
source that does not exist, and a clean table is exactly what stops a reader
asking.

So these test the refusals and the captions, not the formatting.
"""

from __future__ import annotations

import csv

import pytest

from scripts.make_paper_tables import (
    ablation_table,
    as_latex,
    as_markdown,
    control_table,
    demath,
    read_rows,
)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def ablation_rows(**overrides):
    base = {"config": "G", "n_runs": 20, "n_folds": 4, "n_seeds": 5,
            "macro_f1_mean": 0.50, "macro_f1_lo": 0.40, "macro_f1_hi": 0.60,
            "qwk_mean": 0.30, "macro_f1_seed_spread": 0.02}
    base.update(overrides)
    return base


# --------------------------------------------------------------- refusals --


def test_a_missing_source_refuses_and_names_the_command(tmp_path):
    with pytest.raises(SystemExit) as caught:
        read_rows(tmp_path / "nothing.csv", "python scripts/run_loco.py --ablation")
    message = str(caught.value)
    assert "run_loco.py" in message
    assert "looks like a result" in message


def test_a_header_only_source_refuses(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("config,macro_f1_mean\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        read_rows(path, "some command")


# --------------------------------------------------------------- captions --


def test_the_ablation_caption_states_folds_and_seeds():
    _, _, caption = ablation_table([ablation_rows()])
    assert "4 folds" in caption and "5 seeds" in caption
    assert "effective $n$" in caption


def test_the_caption_says_the_interval_is_over_folds_not_sequences():
    """153 sequences and 4 folds are different denominators, and the larger one
    is the one a reader assumes."""
    _, _, caption = ablation_table([ablation_rows()])
    assert "not over sequences" in caption


def test_a_single_seed_table_says_it_is_not_an_ablation():
    _, _, caption = ablation_table([ablation_rows(n_seeds=1,
                                                  macro_f1_seed_spread="")])
    assert "ranks initialisations" in caption


def test_overlapping_seed_spread_is_named_in_the_caption():
    """P54. Two configs 0.01 apart with a 0.20 seed spread are not separated,
    and a ranked table invites a reader to separate them anyway."""
    rows = [ablation_rows(config="B", macro_f1_mean=0.50,
                          macro_f1_seed_spread=0.20),
            ablation_rows(config="E", macro_f1_mean=0.51,
                          macro_f1_seed_spread=0.04)]
    _, _, caption = ablation_table(rows)
    assert "not separated" in caption


def test_a_clean_separation_does_not_get_the_warning():
    rows = [ablation_rows(config="B", macro_f1_mean=0.20,
                          macro_f1_seed_spread=0.01),
            ablation_rows(config="G", macro_f1_mean=0.80,
                          macro_f1_seed_spread=0.01)]
    _, _, caption = ablation_table(rows)
    assert "not separated" not in caption


# ------------------------------------------------------------ disqualified --


def control_row(**overrides):
    base = {"method_a": "fixed", "method_b": "webster", "n_pairs": 30,
            "mean_a": 71.9, "ci_a_low": 66.0, "ci_a_high": 75.7,
            "mean_b": 66.6, "ci_b_low": 64.4, "ci_b_high": 68.8,
            "mean_difference": 5.28, "ci_diff_low": -1.0, "ci_diff_high": 11.0,
            "t": 1.7, "p": 0.0999, "cohens_d": 0.31, "significant": "False",
            "improvement_percent": 7.3, "regime": "saturated",
            "metric": "mean_wait_s", "a_disqualified": "",
            "b_disqualified": "", "citable": "True"}
    base.update(overrides)
    return base


def test_a_disqualified_method_is_shown_as_disqualified_not_dropped():
    """ADR-012 disqualified those methods for a reason, and the reason has to
    travel with the number. Omitting the row would be cherry-picking (§2.5.5);
    printing it plain would be worse."""
    _, body, caption = control_table([control_row(b_disqualified="ADR-012")])
    assert len(body) == 1
    assert "disqualified: webster" in body[0][-1]
    assert "not omitted" in caption


def test_both_sides_disqualified_names_both():
    _, body, _ = control_table([control_row(a_disqualified="x",
                                            b_disqualified="y")])
    assert "fixed" in body[0][-1] and "webster" in body[0][-1]


def test_a_clean_comparison_reports_significance():
    _, body, _ = control_table([control_row(significant="True")])
    assert body[0][-1] == "significant"


def test_the_caption_lists_every_regime_present():
    """A caption naming one regime over a table spanning three is a wrong
    caption, which is harder to catch than a wrong number."""
    rows = [control_row(regime="light"), control_row(regime="saturated"),
            control_row(regime="oversaturated")]
    _, _, caption = control_table(rows)
    for regime in ("light", "saturated", "oversaturated"):
        assert regime in caption


# ------------------------------------------------------------- rendering --


def test_the_two_formats_carry_the_same_caption():
    """Two renderings that can disagree will eventually disagree."""
    header, body, caption = ablation_table([ablation_rows()])
    latex = as_latex(header, body, caption, "ablation")
    markdown = as_markdown(header, body, caption, "ablation")
    assert demath(caption) in markdown
    assert caption in latex


def test_markdown_carries_no_latex_math():
    header, body, caption = control_table([control_row()])
    markdown = as_markdown(header, body, caption, "control")
    for token in ("$", "\\alpha", "\\%", "{,}"):
        assert token not in markdown


def test_latex_is_marked_as_generated():
    header, body, caption = ablation_table([ablation_rows()])
    latex = as_latex(header, body, caption, "ablation")
    assert "do not edit by hand" in latex
    assert "NFR-10" in latex


def test_every_row_has_a_cell_for_every_column():
    header, body, _ = ablation_table([ablation_rows(), ablation_rows(config="A")])
    assert all(len(record) == len(header) for record in body)


# ------------------------------------------------------------- provenance --


def test_a_table_carries_the_digest_of_its_source(tmp_path):
    """A caption is a claim about a run and outlives it unless something ties
    them together. This repository has already shipped one caption that said
    'at saturation' over three regimes."""
    from scripts.make_paper_tables import source_digest

    path = write_csv(tmp_path / "src.csv", [ablation_rows()])
    header, body, caption = ablation_table([ablation_rows()])
    provenance = f"source: {path.as_posix()} sha256:{source_digest(path)}"
    for rendered in (as_latex(header, body, caption, "ablation", provenance),
                     as_markdown(header, body, caption, "ablation", provenance)):
        assert source_digest(path) in rendered
        assert "src.csv" in rendered


def test_the_digest_changes_when_the_source_changes(tmp_path):
    from scripts.make_paper_tables import source_digest

    path = write_csv(tmp_path / "src.csv", [ablation_rows()])
    before = source_digest(path)
    write_csv(path, [ablation_rows(macro_f1_mean=0.51)])
    assert source_digest(path) != before


def test_provenance_is_optional_so_the_builders_stay_usable(tmp_path):
    header, body, caption = ablation_table([ablation_rows()])
    assert r"\begin{table}" in as_latex(header, body, caption, "ablation")


# ------------------------------------------------ gated on the claims file --


def test_the_ablation_table_declares_the_claims_it_depends_on():
    """P67. Numbers from a corpus that fails its own claims gate are a real
    measurement of something other than what the paper reports."""
    from scripts.make_paper_tables import DEPENDS_ON_CLAIMS

    assert "domain" in DEPENDS_ON_CLAIMS["ablation"]
    assert "class_coverage" in DEPENDS_ON_CLAIMS["ablation"]


def test_the_control_table_depends_on_no_corpus_claim():
    """SUMO. No camera, no domain, no class support — gating it on the corpus
    would be a guard that cries wolf."""
    from scripts.make_paper_tables import DEPENDS_ON_CLAIMS

    assert DEPENDS_ON_CLAIMS["control"] == ()


def test_a_table_is_withheld_while_its_claims_fail(tmp_path, monkeypatch, capsys):
    """Not captioned — withheld. A caption cannot stop numbers being pasted
    into a draft three weeks later with the caveats stripped."""
    from scripts import make_paper_tables

    monkeypatch.setattr(make_paper_tables, "failing_claims",
                        lambda table: ([{"id": "domain", "detail": "no on-target camera"}]
                                       if table == "ablation" else []))
    out = tmp_path / "tables"
    assert make_paper_tables.main(
        ["--which", "ablation", "--out", str(out)]) == 1
    assert "NOT RENDERED" in capsys.readouterr().out
    assert not list(out.glob("ablation.*")), (
        "a withheld table must leave no file behind")


def test_a_table_renders_when_its_claims_hold(tmp_path, monkeypatch):
    from scripts import make_paper_tables

    monkeypatch.setattr(make_paper_tables, "failing_claims", lambda table: [])
    out = tmp_path / "tables"
    assert make_paper_tables.main(["--which", "control", "--out", str(out)]) == 0
    assert (out / "control.tex").is_file()


def test_a_baselines_only_control_table_says_so(tmp_path):
    """Rendering is not meaning. A green table with no learned method in it
    reads as 'control is done' to anyone who does not count the rows."""
    _, _, caption = control_table([control_row(method_a="fixed",
                                               method_b="webster")])
    assert "No learned controller" in caption
    assert "P52" in caption


def test_a_table_containing_a_learned_arm_drops_that_sentence():
    _, _, caption = control_table([control_row(method_a="ppo",
                                               method_b="webster")])
    assert "No learned controller" not in caption
