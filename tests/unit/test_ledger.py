"""Unit tests for the effectiveness ledger (meta_harness.ledger)."""

from __future__ import annotations

from pathlib import Path

from meta_harness.ledger import (
    LedgerSummary,
    main,
    render,
    summarize,
    summarize_history,
)
from meta_harness.verdict import Verdict, append_history

_TOML = """\
[project]
language = "python"

[checks]
required = ["00_build"]
"""


def _pass(n: int) -> list[Verdict]:
    return [Verdict(ok=True) for _ in range(n)]


# --- summarize_history (pure) ----------------------------------------------


def test_summarize_empty_history() -> None:
    s = summarize_history("/p", [])
    assert s.runs == 0
    assert s.failures_caught == 0
    assert s.current_streak == 0
    assert s.streak_kind == "none"


def test_summarize_all_green() -> None:
    s = summarize_history("/p", _pass(3))
    assert s.runs == 3
    assert s.failures_caught == 0
    assert s.current_streak == 3
    assert s.streak_kind == "green"


def test_summarize_counts_failures_and_trailing_red_streak() -> None:
    history = [Verdict(ok=True), Verdict(ok=False), Verdict(ok=False)]
    s = summarize_history("/p", history)
    assert s.runs == 3
    assert s.failures_caught == 2
    assert s.current_streak == 2
    assert s.streak_kind == "red"


def test_summarize_uses_the_last_run_not_the_second() -> None:
    # last run differs from the 2nd ⇒ pins that "latest" is history[-1], not history[1].
    history = [Verdict(ok=True), Verdict(ok=True), Verdict(ok=False)]
    s = summarize_history("/p", history)
    assert s.streak_kind == "red"
    assert s.current_streak == 1
    assert s.failures_caught == 1


def test_summarize_streak_resets_at_transition() -> None:
    # ...fail, then pass ⇒ current green streak is 1, but a failure was still caught.
    history = [Verdict(ok=False), Verdict(ok=True)]
    s = summarize_history("/p", history)
    assert s.failures_caught == 1
    assert s.current_streak == 1
    assert s.streak_kind == "green"


# --- render / summarize line -----------------------------------------------


def test_render_empty_is_exact() -> None:
    assert render([]) == "no governed projects with recorded history."


def test_render_row_shows_fields() -> None:
    out = render([LedgerSummary("/x/proj", 5, 2, 3, "green")])
    lines = out.splitlines()
    assert lines[0].split() == ["PROJECT", "RUNS", "CAUGHT", "STREAK"]
    # the row carries every field verbatim, in column order.
    row = lines[2]
    assert row.split() == ["/x/proj", "5", "2", "3", "green"]


def test_render_shortens_home_paths() -> None:
    home = str(Path.home())
    out = render([LedgerSummary(f"{home}/sub/proj", 1, 0, 1, "green")])
    assert "~/sub/proj" in out


def test_render_never_gated_shows_dash() -> None:
    out = render([LedgerSummary("/p", 0, 0, 0, "none")])
    assert "—" in out.splitlines()[2]


def test_summarize_line_counts() -> None:
    rows = [
        LedgerSummary("/a", 4, 1, 2, "green"),
        LedgerSummary("/b", 0, 0, 0, "none"),
        LedgerSummary("/c", 6, 3, 1, "red"),
    ]
    line = summarize(rows)
    assert "3 governed" in line
    assert "2 with history" in line
    assert "10 gate runs" in line
    assert "4 failures caught" in line


# --- main (fs discovery + history read) ------------------------------------


def _write_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "borromeanrings.toml").write_text(_TOML, encoding="utf-8")
    return root


def test_main_renders_recorded_history(tmp_path: Path, capsys) -> None:
    proj = _write_project(tmp_path / "proj")
    append_history(proj, Verdict(ok=True))
    append_history(proj, Verdict(ok=False))
    rc = main([str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "proj" in out
    assert "governed" in out


def test_main_handles_no_projects(tmp_path: Path, capsys) -> None:
    rc = main([str(tmp_path)])
    assert rc == 0
    assert "no governed" in capsys.readouterr().out
