"""Unit tests for the SWE-state report (meta_harness.swe_state; SPEC-swe-state.md).

Exact-value tests: the report is a record, so every line is pinned — what a project
practises, what it lacks, what to adopt next (in the one fixed order), and where each
fact came from. Edge cases follow SPEC §5: never gated ⇒ ``unknown`` (not ``lacks``),
malformed input ⇒ that section says ``unreadable`` and the rest still renders.
"""

from __future__ import annotations

import json

from meta_harness.adopt import RATCHET_BASELINES
from meta_harness.swe_state import (
    Adoption,
    CheckState,
    FeatureFact,
    MatrixRow,
    RowState,
    SweState,
    assess,
    parse_matrices,
    render,
    to_json,
)
from meta_harness.verdict import Verdict

REQUIRED = ("00_build", "14_container", "50_security", "40_test", "32_complexity", "70_pip_audit")
VERDICT = Verdict(
    ok=False,
    checks=(
        ("00_build", "pass"),
        ("14_container", "noop"),
        ("50_security", "fail"),
        ("40_test", "pass"),
    ),
    run_id="r1",
    harness_version="v1",
)
FEATURES = (
    FeatureFact("entrypoint_declared", "an invocable entry point is declared", True, "#79"),
    FeatureFact("usage_documented", "usage is documented in the README", False, "Nielsen #10"),
    FeatureFact("license_present", "a license file is present", True, "ADR-0012"),
)
MATRICES = {
    "03-delivery.md": (
        "# Delivery\n\n"
        "| Row | Criterion (binary or ratchet) | Enforced by | Buildability | Source |\n"
        "|---|---|---|---|---|\n"
        "| D2 | Conventional commits | ✅ `09_commits` (`[collaboration]`) | now | CC 1.0 |\n"
        "| D6 | Gated merge | ✅ `merge.sh` (runs `./verify.sh`) | now | Accelerate |\n"
        "| T1 | Builds and tests | ✅ `00_build` + `40_test` | now | — |\n"
        "not a table line\n"
        "| too | short |\n"
    ),
    "02-security.md": (
        "| Row | Criterion | Enforced by | Buildability | Source |\n"
        "|---|---|---|---|---|\n"
        "| S1 | SAST on every gate | ✅ `50_security` (bandit) | now | SSDF PW.7 |\n"
        "| S2 | Dependencies audited | ✅ `70_pip_audit` (heavy lane) | now | ASVS V14 |\n"
        "| S6 | SBOM produced | gap → #58 (supply chain; see #138) | now | NTIA |\n"
    ),
}
ROWS = parse_matrices(MATRICES)


def _assess(**overrides: object) -> SweState:
    facts: dict[str, object] = {
        "project": "/home/x/proj",
        "required": REQUIRED,
        "verdict": VERDICT,
        "archetypes": ("cli",),
        "features": FEATURES,
        "has_changelog": True,
        "baseline_files_present": (),
        "matrix_rows": ROWS,
    }
    facts.update(overrides)
    return assess(**facts)  # type: ignore[arg-type]


# --- matrix parsing -----------------------------------------------------------------------


def test_parse_matrices_reads_rows_in_file_order_with_checks_and_gaps() -> None:
    expected = (
        MatrixRow("02-security.md", "S1", "SAST on every gate", "✅ `50_security` (bandit)",
                  ("50_security",), ""),
        MatrixRow("02-security.md", "S2", "Dependencies audited",
                  "✅ `70_pip_audit` (heavy lane)", ("70_pip_audit",), ""),
        MatrixRow("02-security.md", "S6", "SBOM produced",
                  "gap → #58 (supply chain; see #138)", (), "#58"),
        MatrixRow("03-delivery.md", "D2", "Conventional commits",
                  "✅ `09_commits` (`[collaboration]`)", ("09_commits",), ""),
        MatrixRow("03-delivery.md", "D6", "Gated merge", "✅ `merge.sh` (runs `./verify.sh`)",
                  (), ""),
        MatrixRow("03-delivery.md", "T1", "Builds and tests", "✅ `00_build` + `40_test`",
                  ("00_build", "40_test"), ""),
    )  # fmt: skip
    assert expected == ROWS


def test_parse_matrices_dedupes_repeated_check_ids_in_one_cell() -> None:
    rows = parse_matrices({"m.md": "| S3 | x | `12_secrets` and `12_secrets` again | now | y |\n"})
    assert rows[0].checks == ("12_secrets",)


def test_parse_matrices_empty_input_is_no_rows() -> None:
    assert parse_matrices({}) == ()


# --- the full report ----------------------------------------------------------------------


def test_check_states_are_the_verdict_verbatim_and_unknown_when_absent() -> None:
    state = _assess()
    assert state.gated is True
    assert state.checks == (
        CheckState("00_build", "pass"),
        CheckState("14_container", "noop"),
        CheckState("50_security", "fail"),
        CheckState("40_test", "pass"),
        CheckState("32_complexity", "unknown"),
        CheckState("70_pip_audit", "unknown"),
    )


def test_practises_section_exact() -> None:
    state = _assess()
    assert state.practises.checks == ("00_build", "40_test")
    assert state.practises.features == (FEATURES[0], FEATURES[2])
    assert state.practises.matrix_rows == ("T1",)


def test_lacks_section_exact() -> None:
    state = _assess()
    assert state.lacks.checks == (
        CheckState("14_container", "noop"),
        CheckState("50_security", "fail"),
    )
    assert state.lacks.recommended == (
        "12_secrets",
        "11_changelog",
        "33_coupling",
        "45_docstrings",
        "01_source_coherence",
        "21_archetype",
    )
    assert state.lacks.ratchets_without_baseline == ("32_complexity",)
    assert state.lacks.features == (FEATURES[1],)
    assert state.lacks.matrix_gaps == (RowState("S6", "gap", "→ #58"),)
    assert state.lacks.matrix_unmet == (
        RowState("S1", "lacking", "50_security: fail"),
        RowState("D2", "not_adopted", "09_commits: not adopted"),
    )
    assert state.matrix_undecidable == ("D6",)


def test_row_naming_a_required_check_absent_from_the_verdict_is_unknown_not_unmet() -> None:
    """S2 names 70_pip_audit: required (heavy) here but never run on the fast lane."""
    state = _assess()
    assert "S2" not in state.practises.matrix_rows
    assert all(r.row != "S2" for r in state.lacks.matrix_unmet)
    gated = _assess(verdict=Verdict(ok=True, checks=VERDICT.checks + (("70_pip_audit", "pass"),)))
    assert "S2" in gated.practises.matrix_rows


def test_ratchet_with_its_baseline_on_disk_is_not_lacking() -> None:
    state = _assess(baseline_files_present=(RATCHET_BASELINES["32_complexity"],))
    assert state.lacks.ratchets_without_baseline == ()


def test_recommended_agrees_with_adopt_when_changelog_is_missing() -> None:
    state = _assess(has_changelog=False)
    assert "11_changelog" in state.lacks.recommended


def test_adopt_next_is_the_fixed_order_and_nothing_else() -> None:
    state = _assess()
    assert state.adopt_next == (
        Adoption("gate", "50_security",
                 "last reported fail; the gate is fail-closed: fix the finding"),
        Adoption("gate", "14_container",
                 "last reported noop; it inspected nothing: point it at something or drop it"),
        Adoption("baseline", "32_complexity",
                 "seed .borromeanrings-complexity-baseline from current state (adopt.sh)"),
        Adoption("check", "12_secrets", "recommended by adopt.sh; add to [checks].required"),
        Adoption("check", "11_changelog", "recommended by adopt.sh; add to [checks].required"),
        Adoption("check", "33_coupling", "recommended by adopt.sh; add to [checks].required"),
        Adoption("check", "45_docstrings", "recommended by adopt.sh; add to [checks].required"),
        Adoption("check", "01_source_coherence",
                 "recommended by adopt.sh; add to [checks].required"),
        Adoption("check", "21_archetype", "recommended by adopt.sh; add to [checks].required"),
        Adoption("feature", "usage_documented", "usage is documented in the README (Nielsen #10)"),
    )  # fmt: skip


def test_sources_cite_every_input() -> None:
    state = _assess()
    assert state.sources.config == "borromeanrings.toml — 6 check(s) required"
    assert state.sources.verdict == (
        ".meta-harness/last_verdict.json — run r1 FAIL by borromeanRings v1"
    )
    assert state.sources.archetypes == "cli — meta_harness.archetypes catalog"
    assert state.sources.matrices == "6 row(s) from 2 matrix file(s); undecidable from receipts: D6"


def test_render_full_report_exact() -> None:
    assert render(_assess()) == "\n".join(
        [
            "SWE state — proj",
            "",
            "Practises",
            "  checks (required, last reported pass): 00_build, 40_test",
            "  checks unknown (not in the last verdict): 32_complexity, 70_pip_audit",
            "  archetype features present (cli): entrypoint_declared, license_present",
            "  matrix rows enforced: T1",
            "",
            "Lacks",
            "  checks required but last reported noop/fail: 14_container (noop),"
            " 50_security (fail)",
            "  recommended by adopt.sh, not required: 12_secrets, 11_changelog, 33_coupling,"
            " 45_docstrings, 01_source_coherence, 21_archetype",
            "  ratchets without a baseline: 32_complexity",
            "  archetype features absent: usage_documented — usage is documented in the README",
            "  matrix rows at a gap: S6 (→ #58)",
            "  matrix rows unmet here: S1 (50_security: fail), D2 (09_commits: not adopted)",
            "",
            "Adopt next",
            "  1. [gate]     50_security — last reported fail; the gate is fail-closed: fix the"
            " finding",
            "  2. [gate]     14_container — last reported noop; it inspected nothing: point it at"
            " something or drop it",
            "  3. [baseline] 32_complexity — seed .borromeanrings-complexity-baseline from current"
            " state (adopt.sh)",
            "  4. [check]    12_secrets — recommended by adopt.sh; add to [checks].required",
            "  5. [check]    11_changelog — recommended by adopt.sh; add to [checks].required",
            "  6. [check]    33_coupling — recommended by adopt.sh; add to [checks].required",
            "  7. [check]    45_docstrings — recommended by adopt.sh; add to [checks].required",
            "  8. [check]    01_source_coherence — recommended by adopt.sh; add to"
            " [checks].required",
            "  9. [check]    21_archetype — recommended by adopt.sh; add to [checks].required",
            "  10. [feature]  usage_documented — usage is documented in the README (Nielsen #10)",
            "",
            "Sources",
            "  config:     borromeanrings.toml — 6 check(s) required",
            "  verdict:    .meta-harness/last_verdict.json — run r1 FAIL by borromeanRings v1",
            "  archetypes: cli — meta_harness.archetypes catalog",
            "  matrices:   6 row(s) from 2 matrix file(s); undecidable from receipts: D6",
            "  ordering:   fixed — gate gaps, then baselines, then recommended, then features;"
            " no score, no ranking",
            "",
        ]
    )


def test_to_json_is_the_report_as_data() -> None:
    data = json.loads(to_json(_assess()))
    assert data["project"] == "/home/x/proj"
    assert data["gated"] is True
    assert data["practises"]["checks"] == ["00_build", "40_test"]
    assert data["adopt_next"][0] == {
        "kind": "gate",
        "subject": "50_security",
        "reason": "last reported fail; the gate is fail-closed: fix the finding",
    }
    assert data["lacks"]["matrix_gaps"] == [{"row": "S6", "state": "gap", "detail": "→ #58"}]


# --- edge cases (SPEC §5) -----------------------------------------------------------------


def test_never_gated_makes_every_check_unknown_not_lacking() -> None:
    state = _assess(verdict=None)
    assert state.gated is False
    assert {c.status for c in state.checks} == {"unknown"}
    assert state.practises.checks == ()
    assert state.lacks.checks == ()
    assert state.practises.matrix_rows == ()
    assert state.lacks.matrix_unmet == ()
    assert state.lacks.matrix_gaps == (RowState("S6", "gap", "→ #58"),)
    assert all(a.kind != "gate" for a in state.adopt_next)
    assert state.adopt_next[0] == Adoption(
        "baseline", "32_complexity",
        "seed .borromeanrings-complexity-baseline from current state (adopt.sh)",
    )  # fmt: skip
    assert state.sources.verdict == "never gated"
    text = render(state)
    assert "  checks (required, last reported pass): unknown — never gated\n" in text
    assert "  checks unknown (not in the last verdict): " + ", ".join(REQUIRED) + "\n" in text
    assert "  checks required but last reported noop/fail: unknown — never gated\n" in text
    assert "  matrix rows enforced: unknown — never gated\n" in text
    assert "  matrix rows unmet here: unknown — never gated\n" in text
    assert "  verdict:    never gated\n" in text


def test_unreadable_verdict_is_named_not_treated_as_never_gated() -> None:
    state = _assess(verdict=None, unreadable=("verdict",))
    assert state.sources.verdict == ".meta-harness/last_verdict.json — unreadable"
    text = render(state)
    assert (
        "  checks (required, last reported pass): unknown — last_verdict.json unreadable\n" in text
    )
    assert "  matrix rows enforced: unknown — last_verdict.json unreadable\n" in text
    assert "Adopt next\n" in text  # the rest still renders


def test_unreadable_config_reports_unreadable_and_still_renders_matrices() -> None:
    state = _assess(
        required=(), verdict=None, archetypes=(), features=(), unreadable=("config", "verdict")
    )
    assert state.checks == ()
    assert state.lacks.recommended == ()
    assert state.lacks.ratchets_without_baseline == ()
    assert state.adopt_next == ()
    assert state.sources.config == "borromeanrings.toml — unreadable"
    assert state.sources.archetypes == "unreadable — borromeanrings.toml"
    text = render(state)
    assert "  checks (required, last reported pass): unreadable — borromeanrings.toml\n" in text
    assert "  checks unknown (not in the last verdict): unreadable — borromeanrings.toml\n" in text
    assert "  recommended by adopt.sh, not required: unreadable — borromeanrings.toml\n" in text
    assert "  ratchets without a baseline: unreadable — borromeanrings.toml\n" in text
    assert "  archetype features present: unreadable — borromeanrings.toml\n" in text
    assert "  archetype features absent: unreadable — borromeanrings.toml\n" in text
    assert "  matrix rows at a gap: S6 (→ #58)\n" in text
    assert "  (nothing to adopt)\n" in text


def test_no_archetypes_declared_says_so() -> None:
    state = _assess(archetypes=(), features=())
    assert state.practises.features == ()
    assert state.lacks.features == ()
    assert all(a.kind != "feature" for a in state.adopt_next)
    assert state.sources.archetypes == "none declared"
    text = render(state)
    assert "  archetype features present: no archetypes declared\n" in text
    assert "  archetype features absent: no archetypes declared\n" in text


def test_archetype_evaluation_failure_is_unreadable_not_absent() -> None:
    state = _assess(features=(), unreadable=("archetypes",))
    assert state.lacks.features == ()
    assert state.sources.archetypes == "cli — unreadable (archetype evaluation failed)"
    text = render(state)
    assert "  archetype features present (cli): unreadable — archetype evaluation failed\n" in text
    assert "  archetype features absent: unreadable — archetype evaluation failed\n" in text


def test_no_matrices_on_disk_is_said_honestly() -> None:
    state = _assess(matrix_rows=None)
    assert state.practises.matrix_rows == ()
    assert state.lacks.matrix_gaps == ()
    assert state.lacks.matrix_unmet == ()
    assert state.matrix_undecidable == ()
    assert state.matrices_on_disk is False
    assert state.sources.matrices == "no matrices on disk"
    text = render(state)
    assert "  matrix rows enforced: no matrices on disk\n" in text
    assert "  matrix rows at a gap: no matrices on disk\n" in text
    assert "  matrix rows unmet here: no matrices on disk\n" in text


def test_unreadable_matrices_render_unreadable() -> None:
    state = _assess(matrix_rows=None, unreadable=("matrices",))
    assert state.sources.matrices == "unreadable"
    text = render(state)
    assert "  matrix rows enforced: unreadable\n" in text
    assert "  matrix rows at a gap: unreadable\n" in text
    assert "  matrix rows unmet here: unreadable\n" in text


def test_everything_practised_renders_none_for_empty_lacks() -> None:
    verdict = Verdict(ok=True, checks=(("00_build", "pass"), ("40_test", "pass")), run_id="r2")
    rows = parse_matrices({"m.md": "| T1 | x | ✅ `00_build` + `40_test` | now | y |\n"})
    state = _assess(
        required=("00_build", "40_test") + tuple(RATCHET_BASELINES) + (
            "12_secrets", "11_changelog", "01_source_coherence", "21_archetype",
        ),
        verdict=Verdict(
            ok=True,
            checks=verdict.checks + tuple((c, "pass") for c in RATCHET_BASELINES)
            + (("12_secrets", "pass"), ("11_changelog", "pass"),
               ("01_source_coherence", "pass"), ("21_archetype", "pass")),
            run_id="r2",
        ),
        features=(FEATURES[0],),
        baseline_files_present=tuple(RATCHET_BASELINES.values()),
        matrix_rows=rows,
    )  # fmt: skip
    assert state.adopt_next == ()
    assert state.sources.verdict == (
        ".meta-harness/last_verdict.json — run r2 PASS by borromeanRings unknown"
    )
    assert state.sources.matrices == "1 row(s) from 1 matrix file(s)"
    text = render(state)
    assert "  checks required but last reported noop/fail: none\n" in text
    assert "  checks unknown (not in the last verdict): none\n" in text
    assert "  recommended by adopt.sh, not required: none\n" in text
    assert "  ratchets without a baseline: none\n" in text
    assert "  archetype features absent: none\n" in text
    assert "  matrix rows at a gap: none\n" in text
    assert "  matrix rows unmet here: none\n" in text
    assert "  matrix rows enforced: T1\n" in text
    assert "  (nothing to adopt)\n" in text


def test_unknown_status_string_counts_as_lacking_fail_closed() -> None:
    """A status the verdict allowlist does not know is failing (ADR-0049) — so it is a lack."""
    state = _assess(verdict=Verdict(ok=False, checks=(("00_build", "bogus"),)))
    assert state.lacks.checks[0] == CheckState("00_build", "bogus")
    assert state.adopt_next[0].subject == "00_build"


def test_project_name_is_the_last_path_segment_even_with_trailing_slash() -> None:
    assert render(_assess(project="/a/b/")).startswith("SWE state — b\n")
    assert render(_assess(project="proj")).startswith("SWE state — proj\n")
