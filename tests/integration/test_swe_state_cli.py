"""End-to-end: ``swe-state.sh`` and ``status.sh --swe`` on a real governed fixture.

The fixture is gated ONCE through the real ``verify.sh`` so its ``last_verdict.json`` is
the gate's own record: ``14_container`` reports ``noop`` (no Dockerfile) and
``21_archetype`` reports ``fail`` (a declared ``cli`` with no documented usage). The
report must then say exactly that — and, in the fixed order, what to adopt next.
See docs/specs/SPEC-swe-state.md §4.5 and §6.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
GATE_TIMEOUT_S = 180

CONFIG = (
    '[project]\nlanguage = "c"\nsrc_dir = "src"\narchetypes = ["cli"]\n\n'
    '[checks]\nrequired = ["14_container", "21_archetype"]\n\n[hygiene]\nrequires = []\n'
)
FILES = {
    "borromeanrings.toml": CONFIG,
    "run.sh": "#!/usr/bin/env bash\necho hi\n",
    "LICENSE": "MIT\n",
    "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n",
}
MATRIX = (
    "| Row | Criterion | Enforced by | Buildability | Source |\n"
    "|---|---|---|---|---|\n"
    "| O3 | HEALTHCHECK declared | ✅ `14_container` rule `healthcheck` | now | CIS |\n"
    "| S6 | SBOM produced | gap → #58 | now | NTIA |\n"
    "| D2 | Conventional commits | ✅ `09_commits` | now | CC |\n"
    "| D6 | Gated merge | ✅ `merge.sh` | now | Accelerate |\n"
)


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


def _gated_fixture(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "proj"
    for rel, content in FILES.items():
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        (project / rel).write_text(content, encoding="utf-8")
    for argv in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(argv, cwd=project, capture_output=True, check=False)
    gate = _run("verify.sh", project)
    assert gate.returncode != 0, gate.stdout  # the archetype feature is missing on purpose
    verdict = json.loads((project / ".meta-harness" / "last_verdict.json").read_text())
    assert dict(map(tuple, verdict["checks"])) == {"14_container": "noop", "21_archetype": "fail"}
    matrices = tmp_path / "matrices"
    matrices.mkdir()
    (matrices / "04-sre.md").write_text(MATRIX, encoding="utf-8")
    (matrices / "README.md").write_text("| X1 | never parsed | `00_build` | | |\n")
    return project, matrices


EXPECTED_PRACTISES = (
    "Practises\n"
    "  checks (required, last reported pass): none\n"
    "  checks unknown (not in the last verdict): none\n"
    "  archetype features present (cli): entrypoint_declared, license_present,"
    " changelog_present\n"
    "  matrix rows enforced: none\n"
)
EXPECTED_LACKS = (
    "Lacks\n"
    "  checks required but last reported noop/fail: 14_container (noop), 21_archetype (fail)\n"
    "  recommended by adopt.sh, not required: 12_secrets, 11_changelog, 32_complexity,"
    " 33_coupling, 45_docstrings, 01_source_coherence\n"
    "  ratchets without a baseline: none\n"
    "  archetype features absent: usage_documented — usage is documented in the README\n"
    "  matrix rows at a gap: S6 (→ #58)\n"
    "  matrix rows unmet here: O3 (14_container: noop), D2 (09_commits: not adopted)\n"
)
EXPECTED_ADOPT = (
    "Adopt next\n"
    "  1. [gate]     21_archetype — last reported fail; the gate is fail-closed: fix the"
    " finding\n"
    "  2. [gate]     14_container — last reported noop; it inspected nothing: point it at"
    " something or drop it\n"
    "  3. [check]    12_secrets — recommended by adopt.sh; add to [checks].required\n"
    "  4. [check]    11_changelog — recommended by adopt.sh; add to [checks].required\n"
    "  5. [check]    32_complexity — recommended by adopt.sh; add to [checks].required\n"
    "  6. [check]    33_coupling — recommended by adopt.sh; add to [checks].required\n"
    "  7. [check]    45_docstrings — recommended by adopt.sh; add to [checks].required\n"
    "  8. [check]    01_source_coherence — recommended by adopt.sh; add to [checks].required\n"
    "  9. [feature]  usage_documented — usage is documented in the README (Nielsen #10 —"
    " help and documentation)\n"
)


def test_swe_state_sh_reports_the_gated_fixture_exactly(tmp_path: Path) -> None:
    project, matrices = _gated_fixture(tmp_path)
    proc = _run("swe-state.sh", project, "--matrices", str(matrices))
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert out.startswith("SWE state — proj\n\n")
    assert EXPECTED_PRACTISES in out
    assert EXPECTED_LACKS in out
    assert EXPECTED_ADOPT in out
    assert "  config:     borromeanrings.toml — 2 check(s) required\n" in out
    assert "  archetypes: cli — meta_harness.archetypes catalog\n" in out
    assert "  matrices:   4 row(s) from 1 matrix file(s); undecidable from receipts: D6\n" in out
    assert " FAIL by borromeanRings " in out

    as_json = json.loads(
        _run("swe-state.sh", project, "--json", "--matrices", str(matrices)).stdout
    )
    assert as_json["gated"] is True
    assert as_json["lacks"]["checks"] == [
        {"check": "14_container", "status": "noop"},
        {"check": "21_archetype", "status": "fail"},
    ]
    assert [a["kind"] for a in as_json["adopt_next"]] == ["gate"] * 2 + ["check"] * 6 + ["feature"]


def test_status_sh_swe_prints_self_status_then_the_report(tmp_path: Path) -> None:
    project, matrices = _gated_fixture(tmp_path)
    proc = _run("status.sh", project, "--swe")
    assert proc.returncode == 0, proc.stderr
    assert "borromeanRings status — proj" in proc.stdout
    assert proc.stdout.index("Last verdict: FAIL") < proc.stdout.index("SWE state — proj")
    assert (
        EXPECTED_LACKS.replace(
            "  matrix rows at a gap: S6 (→ #58)\n"
            "  matrix rows unmet here: O3 (14_container: noop), D2 (09_commits: not adopted)\n",
            "  matrix rows at a gap: no matrices on disk\n"
            "  matrix rows unmet here: no matrices on disk\n",
        )
        in proc.stdout
    )  # status.sh --swe uses the default matrices dir (none on this base)
    assert EXPECTED_ADOPT in proc.stdout


def test_never_gated_and_not_governed_are_said_not_guessed(tmp_path: Path) -> None:
    project = tmp_path / "fresh"
    project.mkdir()
    (project / "borromeanrings.toml").write_text(CONFIG, encoding="utf-8")
    out = _run("swe-state.sh", project).stdout
    assert "  checks (required, last reported pass): unknown — never gated\n" in out
    assert "  checks unknown (not in the last verdict): 14_container, 21_archetype\n" in out
    assert "  checks required but last reported noop/fail: unknown — never gated\n" in out
    assert "  verdict:    never gated\n" in out
    assert "  1. [check]    12_secrets" in out  # no [gate] items without a verdict

    bare = _run("swe-state.sh", tmp_path / "nowhere")
    assert bare.returncode == 0
    assert bare.stdout.startswith("NOT GOVERNED — no borromeanrings.toml in ")


def test_malformed_inputs_are_reported_unreadable(tmp_path: Path) -> None:
    project = tmp_path / "broken"
    (project / ".meta-harness").mkdir(parents=True)
    (project / "borromeanrings.toml").write_text("[checks]\nrequired = []\n", encoding="utf-8")
    (project / ".meta-harness" / "last_verdict.json").write_text("{not json", encoding="utf-8")
    out = _run("swe-state.sh", project).stdout
    assert "  config:     borromeanrings.toml — unreadable\n" in out
    assert "  verdict:    .meta-harness/last_verdict.json — unreadable\n" in out
    assert "  archetypes: unreadable — borromeanrings.toml\n" in out
    assert "  (nothing to adopt)\n" in out
