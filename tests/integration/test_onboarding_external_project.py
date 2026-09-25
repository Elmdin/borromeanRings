"""Adopting this harness on a project that is not this one (audit of 2026-09-20).

borromeanRings has only ever gated its own repository, whose config and baselines are
hand-maintained. An audit ran it against a fresh external project by following the
documented path — `init.sh`, then the gate, then `adopt.sh`, then the gate — and every
step of that path was broken in a way invisible from inside this repo:

* `init.sh` wrote `package = ""`, which silently darkened `32_complexity`, `33_coupling`
  and `45_docstrings`: they reported "no package/source to measure (greenfield)" about a
  project with five modules in `src/`. `adopt.sh` then promoted exactly those three into
  the required set.
* `adopt.sh` seeded the coverage baseline from a receipt that rounds to two decimals,
  while the check compares full precision — so the next run failed with
  `COVERAGE REGRESSION: 97.37% is below baseline 97.37%`.
* `adopt.sh` seeded no baseline for the three ratchets it had just made required, and
  their defaults are permissive, so each printed `PASS` and could never fail.
* `adopt.sh` promoted `17_prior_art`, whose message points at `docs/surveys/TEMPLATE.md`
  — a file that exists in the harness, not in the governed project.

This test is that audit, kept. It is deliberately end-to-end and slow: the bugs lived
precisely in the seams between the three entry points, and nothing narrower saw them.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import tomllib

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
GATE_TIMEOUT_S = 300

MODULES = {
    "models.py": '"""Value types."""\n\n\nclass Entry:\n'
    '    """One ledger entry."""\n\n'
    "    def __init__(self, amount: int, note: str) -> None:\n"
    "        self.amount = amount\n        self.note = note\n",
    "parsing.py": '"""Reading entries from text."""\n\n'
    "from thing.models import Entry\n\n\n"
    "def parse(line: str) -> Entry:\n"
    '    """Parse one "amount note" line."""\n'
    "    amount, _, note = line.partition(' ')\n"
    "    return Entry(int(amount), note)\n",
    "ledger.py": '"""Totals."""\n\n'
    "from thing.models import Entry\n\n\n"
    "def total(entries: list[Entry]) -> int:\n"
    '    """Sum the amounts."""\n'
    "    return sum(entry.amount for entry in entries)\n",
}
INIT = (
    '"""A tiny ledger."""\n\n'
    "from thing.ledger import total\nfrom thing.parsing import parse\n\n"
    '__all__ = ["parse", "total"]\n'
)
TESTS = (
    "from thing import parse, total\n\n\n"
    "def test_parse() -> None:\n    assert parse('5 rent').amount == 5\n\n\n"
    "def test_total() -> None:\n    assert total([parse('5 a'), parse('7 b')]) == 12\n"
)
PYPROJECT = (
    '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n\n'
    '[project]\nname = "thing"\nversion = "0.1.0"\n\n'
    '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
)


def _git(project: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=project,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A realistic external project: src layout, several modules, passing tests, git."""
    root = tmp_path / "thing"
    (root / "src" / "thing").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "thing" / "__init__.py").write_text(INIT, encoding="utf-8")
    for name, body in MODULES.items():
        (root / "src" / "thing" / name).write_text(body, encoding="utf-8")
    (root / "tests" / "test_thing.py").write_text(TESTS, encoding="utf-8")
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (root / "README.md").write_text("# thing\n\nA tiny ledger.\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    # The fixture's own code must be clean, or the gate fails on the fixture rather than
    # on what each test is about (10_format is in the default set).
    formatted = subprocess.run(
        ["ruff", "format", "-q", str(root)], capture_output=True, text=True, check=False
    )
    assert formatted.returncode == 0, formatted.stderr
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "chore: the project")
    return root


def _run(script: str, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(BORROMEANRINGS_HOME / script), *args, str(project)],
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )


def _gate(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(BORROMEANRINGS_HOME / "verify.sh")],
        cwd=project,
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )


def _receipts(project: Path) -> dict[str, dict]:
    run_dir = sorted((project / ".meta-harness" / "receipts").glob("*/"))[-1]
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in run_dir.glob("*.json")}


def _config(project: Path) -> dict:
    return tomllib.loads((project / "borromeanrings.toml").read_text(encoding="utf-8"))


def test_init_names_the_package_it_can_see(project: Path) -> None:
    """`package = ""` is not a neutral default: it switches off every check that
    measures the project's own code, while the gate still reports PASS."""
    out = _run("init.sh", project)

    assert out.returncode == 0, out.stdout + out.stderr
    assert _config(project)["project"]["package"] == "thing"


def test_the_checks_that_measure_code_actually_measure_it(project: Path) -> None:
    """The three package-bound ratchets said "greenfield — nothing to analyze" about a
    project with four modules, because of that empty default."""
    _run("init.sh", project)
    _run("adopt.sh", project)

    _gate(project)

    receipts = _receipts(project)
    for check in ("32_complexity", "33_coupling", "45_docstrings"):
        assert receipts[check]["status"] != "noop", (
            f"{check} inspected nothing on a project with four modules: "
            f"{receipts[check].get('summary')}"
        )


def test_the_gate_is_green_immediately_after_adopt(project: Path) -> None:
    """The worst thing a new adopter met: `adopt.sh` made a clean project red with
    `COVERAGE REGRESSION: 97.37% is below baseline 97.37%` — the baseline seeded from a
    receipt rounded to two decimals, the check comparing full precision."""
    _run("init.sh", project)
    assert _gate(project).returncode == 0, "the project is clean before adopting"

    adopted = _run("adopt.sh", project)
    proc = _gate(project)

    assert proc.returncode == 0, adopted.stdout + "\n" + proc.stdout
    assert "REGRESSION" not in proc.stdout


def test_adopt_seeds_a_baseline_for_every_ratchet_it_makes_required(project: Path) -> None:
    """A ratchet with no baseline defaults to permissive, prints PASS, and can never
    fail. Promoting one without seeding it is how the audit's complexity regression went
    uncaught on the documented path.

    The path is init, gate, adopt: adoption never runs a language's test tool itself, so
    the coverage baseline can only come from a run that measured coverage — which is what
    adopt.sh tells you when there is none."""
    _run("init.sh", project)
    _gate(project)
    _run("adopt.sh", project)

    required = _config(project)["checks"]["required"]
    for check, baseline in (
        ("32_complexity", ".borromeanrings-complexity-baseline"),
        ("33_coupling", ".borromeanrings-coupling-baseline"),
        ("45_docstrings", ".borromeanrings-docstring-baseline"),
        ("40_test", ".borromeanrings-coverage-baseline"),
        ("19_context_budget", ".borromeanrings-context-baseline"),
    ):
        if check in required:
            assert (project / baseline).is_file(), f"{check} is required with no baseline"


def test_a_real_complexity_regression_is_caught_on_the_documented_path(project: Path) -> None:
    """The end of that chain: with the baseline seeded, the ratchet does its job."""
    _run("init.sh", project)
    _run("adopt.sh", project)
    _git(project, "checkout", "-q", "-b", "feat/tangle")
    nested = (
        '"""Deeply nested."""\n\n\ndef tangle(rows: list[int]) -> int:\n'
        '    """Count."""\n    n = 0\n'
    )
    for depth in range(1, 8):
        nested += "    " * depth + f"for x{depth} in rows:\n"
    nested += "    " * 8 + "n += 1\n    return n\n"
    (project / "src" / "thing" / "tangle.py").write_text(nested, encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "feat: tangle")

    proc = _gate(project)

    assert proc.returncode != 0, proc.stdout
    assert _receipts(project)["32_complexity"]["status"] == "fail", proc.stdout


def test_adopt_gives_the_project_what_its_promoted_checks_ask_for(project: Path) -> None:
    """`17_prior_art` tells the reader to write a survey "see docs/surveys/TEMPLATE.md",
    a path that existed only inside the harness. A check promoted to required must not
    point at a file the governed project has never had."""
    _run("init.sh", project)
    adopted = _run("adopt.sh", project)

    if "17_prior_art" in _config(project)["checks"]["required"]:
        template = project / "docs" / "surveys" / "TEMPLATE.md"
        assert template.is_file(), adopted.stdout
        assert template.read_text(encoding="utf-8").strip(), "the template is empty"


def test_a_green_run_says_how_much_of_it_inspected_nothing(project: Path) -> None:
    """The first green run executed 36 checks, 16 of which inspected nothing, and said
    so nowhere: the count only covered the required set, which is empty of noops at that
    point. An adopter reads PASS and ships (ADR-0049)."""
    _run("init.sh", project)

    proc = _gate(project)

    receipts = _receipts(project)
    noops = [cid for cid, r in receipts.items() if r.get("status") == "noop"]
    assert noops, "this fixture is expected to have some honest noops"
    assert "also inspected nothing" in proc.stdout, proc.stdout
    assert str(len(noops)) in proc.stdout, (
        f"{len(noops)} of {len(receipts)} checks inspected nothing; the verdict said: "
        + "".join(line for line in proc.stdout.splitlines(keepends=True) if "NOTHING" in line)
    )
