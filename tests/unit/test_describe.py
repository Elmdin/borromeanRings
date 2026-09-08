"""Unit tests for the capability self-description core (to become meta_harness.describe).

The report must be GENERATED from sources of truth — the check registry on disk, the
spine, the ADR directory — never from hand-written prose. These tests pin that: every
fact in the output must be traceable to a file the test wrote. See #132.
"""

from __future__ import annotations

from pathlib import Path

from meta_harness.describe import (
    BLOCK_BEGIN,
    BLOCK_END,
    CheckInfo,
    count_claims,
    discover_checks,
    gather,
    main,
    matrices,
    number_word,
    render_report,
    replace_block,
    summary_block,
)


def _script(root: Path, lane: str, name: str, body: str) -> None:
    d = root / lane
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")


# --- discover_checks: the registry is the scripts on disk -------------------------------


def test_discovers_id_and_cmd_from_a_check_script(tmp_path: Path) -> None:
    _script(
        tmp_path,
        "shared",
        "05_hygiene.sh",
        'id="05_hygiene"\ncmd="project hygiene (declared paths exist)"\n',
    )
    found = discover_checks(tmp_path)
    assert found == [
        CheckInfo("05_hygiene", "project hygiene (declared paths exist)", "shared", False)
    ]


def test_falls_back_to_run_check_for_inline_scripts(tmp_path: Path) -> None:
    """Five checks never set id=/cmd=; they call run_check directly."""
    _script(tmp_path, "python", "20_lint.sh", 'run_check "20_lint" "ruff" "ruff check ."\n')
    (found,) = discover_checks(tmp_path)
    assert found.id == "20_lint"
    assert "ruff" in found.enforces


def test_header_comment_is_preferred_for_inline_scripts(tmp_path: Path) -> None:
    """A run_check that passes a VARIABLE would otherwise render as a literal `$cmd`."""
    _script(
        tmp_path,
        "python",
        "00_build.sh",
        "# Build / installable: the source compiles and the package imports.\n"
        'cmd="python3 -m compileall"\nrun_check "00_build" "python3" "$cmd"\n',
    )
    (found,) = discover_checks(tmp_path)
    assert found.id == "00_build"
    assert found.enforces.startswith("Build / installable")
    assert "$cmd" not in found.enforces


def test_header_comment_strips_the_id_prefix(tmp_path: Path) -> None:
    body = (
        "# 16_shellcheck — lint the project's own shell.\n"
        + 'run_check "16_shellcheck" "shellcheck" "$args"\n'
    )
    _script(tmp_path, "shared", "16_shellcheck.sh", body)
    (found,) = discover_checks(tmp_path)
    assert found.enforces == "lint the project's own shell."


def test_ratchets_are_derived_from_the_text_not_listed(tmp_path: Path) -> None:
    _script(
        tmp_path, "python", "40_test.sh", 'id="40_test"\ncmd="pytest --cov (ratchet vs baseline)"\n'
    )
    (found,) = discover_checks(tmp_path)
    assert found.ratchet is True


def test_lanes_and_ordering_are_stable(tmp_path: Path) -> None:
    _script(tmp_path, "ci", "60_mutation.sh", 'id="60_mutation"\ncmd="mutmut"\n')
    _script(tmp_path, "shared", "05_hygiene.sh", 'id="05_hygiene"\ncmd="h"\n')
    _script(tmp_path, "python", "10_format.sh", 'run_check "10_format" "ruff" "x"\n')
    ids = [c.id for c in discover_checks(tmp_path)]
    assert ids == ["05_hygiene", "10_format", "60_mutation"]  # numeric order across lanes


def test_a_script_declaring_nothing_is_reported_not_dropped(tmp_path: Path) -> None:
    """Silently omitting a check would be the exact drift this exists to stop."""
    _script(tmp_path, "shared", "99_mystery.sh", "echo hi\n")
    (found,) = discover_checks(tmp_path)
    assert found.id == "99_mystery"
    assert "undeclared" in found.enforces


# --- matrices: parsed from the one hand-maintained source, never invented ------------


def test_matrices_parsed_from_the_coverage_map() -> None:
    text = (
        "## 6. Beyond code quality\n\n| Matrix | Status | First real rows |\n|---|---|---|\n"
        "| **Security & compliance** | partial | SAST |\n"
        "| **Product / UX** | archetype | a11y |\n\n## 4. Next\n"
    )
    assert matrices(text) == [("Security & compliance", "partial"), ("Product / UX", "archetype")]


def test_matrices_absent_section_is_empty_not_fabricated() -> None:
    assert matrices("# nothing here\n") == []


# --- count_claims: what the README asserts, so a gate can check it --------------------


def test_count_claims_reads_both_forms() -> None:
    readme = "blah **30 checks** across lanes ... required (twenty gates on this repo)"
    assert count_claims(readme) == {"checks": 30, "gates": 20}


def test_count_claims_missing_is_none_not_zero() -> None:
    assert count_claims("no numbers here") == {}


def test_number_words_up_to_forty() -> None:
    assert number_word("eight") == 8
    assert number_word("twenty") == 20
    assert number_word("thirty-two") == 32
    assert number_word("nonsense") is None


# --- render_report: every fact traceable ---------------------------------------------


def test_report_names_every_check_and_matrix_and_marks_required() -> None:
    checks = [
        CheckInfo("05_hygiene", "hygiene", "shared", False),
        CheckInfo("40_test", "pytest (ratchet)", "python", True),
        CheckInfo("60_mutation", "mutmut (ratchet)", "ci", True),
    ]
    text = render_report(
        checks,
        required=("05_hygiene", "40_test"),
        heavy=("60_mutation",),
        adr_count=51,
        matrix_rows=[("Security & compliance", "partial")],
        commands=["verify.sh", "status.sh"],
        skills=["borromeanrings-status"],
    )
    for needle in (
        "05_hygiene",
        "40_test",
        "60_mutation",
        "Security & compliance",
        "51",
        "verify.sh",
        "borromeanrings-status",
    ):
        assert needle in text
    assert "3 checks" in text
    assert "2 required" in text
    assert "ratchet" in text.lower()


# --- gather + main: the I/O edge, against a fixture harness -----------------------------


def _fixture_home(root: Path) -> Path:
    _script(root / "checks", "shared", "05_hygiene.sh", 'id="05_hygiene"\ncmd="hygiene"\n')
    _script(root / "checks", "python", "40_test.sh", 'id="40_test"\ncmd="pytest (ratchet)"\n')
    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "adr" / "0001-x.md").write_text("# ADR-0001\n", encoding="utf-8")
    (root / "docs" / "ENFORCEMENT-COVERAGE.md").write_text(
        "## 6. Beyond\n\n| M | S | R |\n|---|---|---|\n| **Security** | partial | x |\n\n## 7\n",
        encoding="utf-8",
    )
    (root / "verify.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (root / ".claude" / "skills" / "borromeanrings-status").mkdir(parents=True)
    (root / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["05_hygiene"]\nheavy = []\n', encoding="utf-8"
    )
    return root


def test_gather_reads_every_source_of_truth(tmp_path: Path) -> None:
    home = _fixture_home(tmp_path / "home")
    data = gather(home, home)
    assert [c.id for c in data["checks"]] == ["05_hygiene", "40_test"]
    assert data["required"] == ("05_hygiene",)
    assert data["adr_count"] == 1
    assert data["matrix_rows"] == [("Security", "partial")]
    assert data["commands"] == ["verify.sh"]
    assert data["skills"] == ["borromeanrings-status"]


def test_gather_degrades_when_a_project_has_no_spine(tmp_path: Path) -> None:
    """An ungoverned project still gets the harness description; just nothing 'required'."""
    home = _fixture_home(tmp_path / "home")
    plain = tmp_path / "plain"
    plain.mkdir()
    data = gather(home, plain)
    assert data["required"] == () and len(data["checks"]) == 2


def test_main_renders_markdown_and_json(tmp_path: Path, capsys, monkeypatch) -> None:
    home = _fixture_home(tmp_path / "home")
    monkeypatch.setenv("BORROMEANRINGS_HOME", str(home))
    monkeypatch.setenv("BORROMEANRINGS_PROJECT", str(home))
    assert main([]) == 0
    md = capsys.readouterr().out
    assert "05_hygiene" in md and "Security" in md and "2 checks" in md
    assert main(["--json"]) == 0
    import json

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["adr_count"] == 1 and parsed["checks"][0]["id"] == "05_hygiene"


# --- the README block: generated, marker-scoped, never touching surrounding prose --------

CHECKS3 = [
    CheckInfo("05_hygiene", "h", "shared", False),
    CheckInfo("40_test", "t (ratchet)", "python", True),
    CheckInfo("60_mutation", "m (ratchet)", "ci", True),
]


def test_summary_block_states_the_counts_the_guard_will_check() -> None:
    block = summary_block(
        CHECKS3,
        required=("05_hygiene", "40_test"),
        heavy=("60_mutation",),
        matrix_rows=[("Security", "partial")],
    )
    assert "**3 checks**" in block and "**2 are required" in block
    assert "1 shared, 1 Python, 1 heavy/CI" in block
    assert "2 are threshold-free ratchets" in block
    assert "Security (partial)" in block
    assert block.startswith(BLOCK_BEGIN) and block.endswith(BLOCK_END)


def test_replace_block_touches_only_the_marked_region() -> None:
    readme = "# Title\n\nintro\n\n<!-- describe:begin -->\nOLD\n<!-- describe:end -->\n\nfooter\n"
    out = replace_block(readme, "<!-- describe:begin -->\nNEW\n<!-- describe:end -->")
    assert "OLD" not in out and "NEW" in out
    assert out.startswith("# Title\n\nintro\n\n") and out.endswith("\n\nfooter\n")


def test_replace_block_appends_when_no_markers_exist() -> None:
    out = replace_block("# Title\n", "<!-- describe:begin -->\nX\n<!-- describe:end -->")
    assert out.startswith("# Title\n") and "X" in out and out.endswith("<!-- describe:end -->\n")


def test_replace_block_is_idempotent() -> None:
    block = "<!-- describe:begin -->\nX\n<!-- describe:end -->"
    once = replace_block("# T\n", block)
    assert replace_block(once, block) == once


# --- edge paths: every branch of the parsers is exercised (coverage ratchet is 100) ----


def test_header_comment_stops_at_first_code_line() -> None:
    from meta_harness.describe import _header_comment

    # code before any comment ⇒ no header (the comment further down is NOT the summary)
    assert _header_comment("#!/usr/bin/env bash\nset -u\n# late comment\n") == ""
    # comment lines that are only '#' are skipped until a real one appears
    assert _header_comment("#!/usr/bin/env bash\n#\n# real summary\n") == "real summary"
    # nothing in the window at all
    assert _header_comment("#!/usr/bin/env bash\n") == ""


def test_number_word_handles_tens_and_compounds() -> None:
    assert number_word("thirty") == 30
    assert number_word("thirty-five") == 35
    assert number_word("thirty-twelve") is None  # not a valid compound
    assert number_word("gazillion") is None


def test_count_claims_ignores_a_non_numeric_gate_word() -> None:
    # "(several gates" matches the shape but is not a number ⇒ no claim, not a crash.
    assert "gates" not in count_claims("The required set (several gates on this repo).")
