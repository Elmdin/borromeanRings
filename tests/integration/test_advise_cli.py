"""End-to-end: ``advise.sh`` and ``status.sh --advise`` on a real governed fixture.

The fixture is gated ONCE through the real ``verify.sh`` so its ``last_verdict.json`` is
the gate's own record: ``14_container`` reports ``noop`` (no Dockerfile) and
``21_archetype`` reports ``fail`` (a declared ``web-api`` with none of its required
features). The advice must then say exactly that — the questions first, then the
approaches, each in catalog order. See docs/specs/SPEC-approach-advisor.md §4.5 and §6.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from meta_harness.advisor import CATALOG

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
GATE_TIMEOUT_S = 180

# The fixture declares the checks the diff-keyed rules cite, and switches on each one's
# own opt-in sub-rule, so the end-to-end run proves those rules key on what is really in
# force here — not on the mere shape of the diff.
CONFIG = (
    '[project]\nlanguage = "c"\nsrc_dir = "src"\narchetypes = ["web-api"]\n\n'
    "[checks]\nrequired = "
    '["08_branch", "11_changelog", "13_adr", "14_container", "21_archetype"]\n\n'
    '[collaboration]\nbranch_patterns = ["feat/*", "fix/*"]\n\n'
    "[changelog]\nenabled = true\nrequire_entry_on_src_change = true\n\n"
    "[hygiene]\nrequires = []\n"
)
FILES = {
    "borromeanrings.toml": CONFIG,
    "src/app.c": "int main(void) { return 0; }\n",
    "LICENSE": "MIT\n",
    "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n",
}


def test_every_rule_source_names_an_existing_check_spec_or_adr() -> None:
    """Catalog integrity against the real base: every citation resolves to a file here.

    Lives in the integration suite because it reads the repository by path — mutmut copies
    only ``src/`` and ``tests/`` into its sandbox, so a path-reading test in the unit suite
    would fail the clean-test run and evaluate zero mutants (the heavy lane caught exactly
    that). This suite is mutmut-ignored, and it always runs from the real tree, so the
    guarantee can never silently degrade into a skip.
    """
    check_ids = {p.stem for p in BORROMEANRINGS_HOME.glob("checks/*/[0-9][0-9]_*.sh")}
    specs = {p.name for p in (BORROMEANRINGS_HOME / "docs" / "specs").glob("SPEC-*.md")}
    adrs = {
        p.name[:4] for p in (BORROMEANRINGS_HOME / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")
    }
    assert check_ids and specs and adrs  # the tree is really there; never a vacuous pass
    for rule in CATALOG:
        src = rule.source
        if src.startswith("SPEC-"):
            assert src in specs, f"{rule.id}: {src} is not a spec on this base"
        elif src.startswith("ADR-"):
            assert src[4:] in adrs, f"{rule.id}: {src} is not an ADR on this base"
        else:
            assert src in check_ids, f"{rule.id}: {src} is not a check id on this base"


def _run(script: str, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    return subprocess.run(
        ["bash", str(BORROMEANRINGS_HOME / script), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )


def _git(project: Path, *argv: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *argv],
        cwd=project,
        capture_output=True,
        check=False,
    )


def _gated_fixture(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    for rel, content in FILES.items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(content, encoding="utf-8")
    _git(project, "init", "-q", "-b", "main")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "init")
    _git(project, "checkout", "-qb", "feat/thing")
    (project / "src" / "thing.c").write_text("int thing(void) { return 1; }\n", encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "feat: thing")
    gate = _run("verify.sh", project)
    assert gate.returncode != 0, gate.stdout  # the archetype features are missing on purpose
    verdict = json.loads((project / ".meta-harness" / "last_verdict.json").read_text())
    assert dict(map(tuple, verdict["checks"])) == {
        "08_branch": "pass",
        "11_changelog": "fail",
        "13_adr": "fail",
        "14_container": "noop",
        "21_archetype": "fail",
    }
    return project


EXPECTED_QUESTIONS = (
    "Questions to ask before proceeding\n"
    "  1. enforcement is MANUAL here — the gate runs only when invoked; should the hooks be"
    " wired before you begin (the user's decision, not yours)?  [SPEC-self-status.md]\n"
    "  2. 14_container inspected NOTHING last run — is there truly nothing to inspect, or"
    " should each be pointed at something (or dropped from [checks].required)?  [ADR-0049]\n"
)
EXPECTED_APPROACHES = (
    "Approaches that fit this change\n"
    "  1. the last verdict fails on 11_changelog (fail), 13_adr (fail), 21_archetype (fail) ⇒"
    " the gate is fail-closed: fix those findings before adding anything new  [ADR-0049]\n"
    "  2. new surface on 'feat/thing' touches src/thing.c and no docs/adr/ file ⇒ decide"
    " first, on the record: a SPEC under docs/specs and an ADR under docs/adr before the"
    " code (13_adr fails closed without one)  [13_adr]\n"
    "  3. src/thing.c changed and CHANGELOG.md did not ⇒ write the [Unreleased] entry with"
    " the change, not at release time (11_changelog requires it on a source change)"
    "  [11_changelog]\n"
    "  4. archetype web-api with no health route ⇒ add /livez and /readyz before the feature"
    " (21_archetype fails closed on health_endpoint_declared)  [SPEC-archetypes.md]\n"
    "  5. archetype(s) web-api lack required feature(s) structured_logging_configured —"
    " structured logging is configured (O7 — logs are structured event streams),"
    " input_validation_layer — a boundary input-validation layer is declared (#79 web-api"
    " row 1; OWASP ASVS V5), auth_mechanism_declared — an authentication mechanism is"
    " declared (#79 web-api row 2; ASVS V2/V4), rate_limiter_declared — a rate limiter is"
    " declared (#79 web-api row 3), error_handler_declared — a non-leaking error handler is"
    " declared (#79 web-api row 4; U14), config_from_environment — configuration is read"
    " from the environment (O5 — config in the environment (Twelve-Factor III)),"
    " api_spec_present — the API surface is specified (ASVS V13 — a documented API surface)"
    " ⇒ add them before the feature; 21_archetype fails closed until they exist"
    "  [21_archetype]\n"
    "  6. archetype(s) web-api declared ⇒ read the catalog playbook for each"
    " (meta_harness.archetypes.CATALOG[name].playbook) before designing the change"
    "  [ADR-0062]\n"
    "  7. RECOMMENDED checks 12_secrets, 32_complexity, 33_coupling, 45_docstrings,"
    " 01_source_coherence are not required here ⇒ adopt.sh adds them and seeds their"
    " baselines; propose it, do not apply it silently  [ADR-0041]\n"
)
# 40_test is not required by this C fixture, so nothing claims it ratchets anything here —
# the adoption gate the review found missing, observed end to end.
UNADOPTED_CLAIMS = ("40_test ratchets coverage", "08_branch fails closed")
EXPECTED_FACTS = (
    "Facts: gated=yes · archetypes: web-api · branch: feat/thing · enforcement: manual ·"
    " failing: 11_changelog (fail), 13_adr (fail), 21_archetype (fail) · noop: 14_container ·"
    " changed: 1 path(s) · stakes: (no charter)\n"
    "Order: fixed — questions, then approaches, each in catalog order; no score, no ranking\n"
)


def test_advise_sh_reports_the_gated_fixture_exactly(tmp_path: Path) -> None:
    project = _gated_fixture(tmp_path)
    proc = _run("advise.sh", project)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == (
        "borromeanRings — approach advice for proj   (advisory; never a gate)\n\n"
        + EXPECTED_QUESTIONS
        + "\n"
        + EXPECTED_APPROACHES
        + "\n"
        + EXPECTED_FACTS
    )

    as_json = json.loads(_run("advise.sh", project, "--json").stdout)
    assert as_json["note"] == ""
    assert as_json["facts"]["changed"] == ["src/thing.c"]
    assert as_json["facts"]["failing"] == [
        ["11_changelog", "fail"],
        ["13_adr", "fail"],
        ["21_archetype", "fail"],
    ]
    assert [q["rule"] for q in as_json["questions"]] == ["q_enforcement_off", "q_hollow_checks"]
    assert [a["rule"] for a in as_json["approaches"]] == [
        "a_failing_gate",
        "a_spec_and_adr_first",
        "a_changelog_with_change",
        "a_web_api_health",
        "a_archetype_features",
        "a_playbook",
        "a_recommended",
    ]
    assert as_json["facts"]["live"] == [
        "08_branch",
        "11_changelog",
        "13_adr",
        "14_container",
        "21_archetype",
    ]
    assert all(claim not in _run("advise.sh", project).stdout for claim in UNADOPTED_CLAIMS)


def test_status_sh_advise_prints_self_status_then_the_advice(tmp_path: Path) -> None:
    project = _gated_fixture(tmp_path)
    proc = _run("status.sh", project, "--advise")
    assert proc.returncode == 0, proc.stderr
    assert "borromeanRings status — proj" in proc.stdout
    assert proc.stdout.index("Last verdict: FAIL") < proc.stdout.index(
        "borromeanRings — approach advice for proj"
    )
    assert EXPECTED_QUESTIONS in proc.stdout
    assert EXPECTED_APPROACHES in proc.stdout
    assert EXPECTED_FACTS in proc.stdout


def test_never_gated_and_not_governed_are_said_not_guessed(tmp_path: Path) -> None:
    project = tmp_path / "fresh"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    out = _run("advise.sh", project).stdout
    assert "  1. this project has never been gated — run verify.sh before starting" in out
    assert "  [SPEC-self-status.md]\n" in out
    assert "Facts: gated=no · archetypes: web-api · branch: none · enforcement: manual" in out

    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "borromeanrings.toml").write_text(
        CONFIG.replace('archetypes = ["web-api"]\n', ""), encoding="utf-8"
    )
    assert _run("advise.sh", bare).stdout == (
        "borromeanRings — approach advice for bare   (advisory; never a gate)\n\n"
        "  no advice: never gated, no archetypes\n\n"
        "Facts: gated=no · archetypes: none · branch: none · enforcement: manual ·"
        " failing: none · noop: none · changed: 0 path(s) · stakes: (no charter)\n"
        "Order: fixed — questions, then approaches, each in catalog order; no score, no ranking\n"
    )

    nowhere = _run("advise.sh", tmp_path / "nowhere")
    assert nowhere.returncode == 0
    assert nowhere.stdout.startswith("NOT GOVERNED — no borromeanrings.toml in ")


def test_malformed_and_unknown_archetype_become_a_question(tmp_path: Path) -> None:
    project = tmp_path / "broken"
    (project / ".meta-harness").mkdir(parents=True)
    (project / "borromeanrings.toml").write_text(
        '[project]\narchetypes = ["spaceship"]\n\n[checks]\nrequired = []\n', encoding="utf-8"
    )
    (project / ".meta-harness" / "last_verdict.json").write_text("{not json", encoding="utf-8")
    out = _run("advise.sh", project).stdout
    assert (
        "  1. config, verdict could not be read — fix the record (borromeanrings.toml /"
        " .meta-harness/last_verdict.json) before building on it?  [SPEC-swe-state.md]\n"
    ) in out
    assert "Approaches that fit this change\n  (none)\n" in out


def test_charter_when_present_asks_for_a_reviewer_and_prefers_the_heavy_lane(
    tmp_path: Path,
) -> None:
    project = tmp_path / "charter"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(
        CONFIG + '\n[charter]\nstakes = "high"\n', encoding="utf-8"
    )
    out = _run("advise.sh", project).stdout
    assert (
        "  2. stakes are high and no reviewer is named — who reviews and merges this"
        " (merge.sh is explicit and human)?  [ADR-0007]\n"
    ) in out
    assert (
        ". stakes are high ⇒ run the heavy lane (verify.sh --heavy: mutation, CVE audit,"
        " licences, secret history) before the PR, not just the fast gate  [ADR-0033]\n"
    ) in out
    assert "· stakes: high\n" in out
