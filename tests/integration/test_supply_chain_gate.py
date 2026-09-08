"""End-to-end: the heavy lane gates lockfile integrity and dependency pins. ADR-0061.

Runs the real ``verify.sh --heavy`` against fixture git repos and asserts the receipt
each supply-chain check writes, plus the gate's verdict:

* manifest changed, lockfile unchanged ⇒ ``76_lockfile`` **fail**, gate red;
* both changed ⇒ pass; nothing declared ⇒ ``noop`` (reported as inspected-nothing);
* declared-but-missing lockfile and a broken git index ⇒ fail closed;
* ``78_pins``: an unbounded requirement fails naming the line; bounded passes; no
  dependencies ⇒ ``noop``.

The fixtures' heavy set is only the two checks under test. The other heavy scripts
still execute (verify.sh runs the whole ``checks/ci`` directory), so the environment
carries an offline ``pip_audit`` module stub and a no-op ``mutmut`` on PATH: their
receipts are not in the verdict, and without the stubs 70_pip_audit would hit the
network on every fixture. See docs/specs/SPEC-supply-chain.md.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 180


def _config(lockfile: str) -> str:
    return (
        '[project]\nlanguage = "python"\nsrc_dir = "src"\n\n'
        '[checks]\nrequired = ["01_source_coherence"]\nheavy = ["76_lockfile", "78_pins"]\n\n'
        "[hygiene]\nrequires = []\n\n"
        f'[supply_chain]\nlockfile = "{lockfile}"\n'
    )


def _pyproject(dependency: str | None) -> str:
    deps = "" if dependency is None else f'dependencies = ["{dependency}"]\n'
    return f'[project]\nname = "fixture"\nversion = "0.1"\n{deps}'


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root,
        capture_output=True,
        check=True,
    )


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _project(root: Path, base: dict[str, str], feature: dict[str, str]) -> Path:
    """A repo with ``base`` committed on main and ``feature`` committed on feat/x."""
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _write(root, base)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _git(root, "checkout", "-qb", "feat/x")
    _write(root, feature)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "feature", "--allow-empty")
    return root


def _stubs(tmp_path: Path) -> dict[str, str]:
    """PATH/PYTHONPATH additions that keep the other heavy checks offline and instant."""
    binaries = tmp_path / "stub-bin"
    binaries.mkdir()
    mutmut = binaries / "mutmut"
    mutmut.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    mutmut.chmod(0o755)
    modules = tmp_path / "stub-py" / "pip_audit"
    modules.mkdir(parents=True)
    (modules / "__init__.py").write_text("", encoding="utf-8")
    (modules / "__main__.py").write_text('print("[]")\n', encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = f"{binaries}{os.pathsep}{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(tmp_path / "stub-py")
    return env


def _run_heavy(project: Path, env: dict[str, str]) -> tuple[int, str, dict[str, str], Path]:
    """Run the real heavy gate; return (exit, stdout, {check: status}, receipt dir)."""
    env = dict(env)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY), "--heavy"],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    run_dirs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    latest = run_dirs[-1]
    # Receipts are <check>.json; a tool's raw report (<check>.report.json) is not one.
    statuses = {
        receipt.stem: json.loads(receipt.read_text(encoding="utf-8")).get("status", "?")
        for receipt in latest.glob("*.json")
        if "." not in receipt.stem
    }
    return proc.returncode, proc.stdout, statuses, latest


def test_manifest_changed_without_lockfile_fails_the_heavy_gate(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "stale",
        {
            "borromeanrings.toml": _config("uv.lock"),
            "pyproject.toml": _pyproject("requests>=2,<3"),
            "uv.lock": "version = 1\n",
        },
        {"pyproject.toml": _pyproject("requests")},
    )
    code, stdout, statuses, receipts = _run_heavy(project, _stubs(tmp_path))
    assert code != 0, f"a stale lockfile must fail the heavy gate:\n{stdout}"
    assert statuses["76_lockfile"] == "fail"
    log = (receipts / "76_lockfile.log").read_text(encoding="utf-8")
    assert "pyproject.toml" in log and "uv.lock" in log
    # The same fixture dropped the upper bound: 78_pins names the exact line.
    assert statuses["78_pins"] == "fail"
    pins_log = (receipts / "78_pins.log").read_text(encoding="utf-8")
    assert "'requests'" in pins_log and "no version specifier" in pins_log
    assert "RESULT: FAIL" in stdout


def test_manifest_and_lockfile_changed_together_pass(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "fresh",
        {
            "borromeanrings.toml": _config("uv.lock"),
            "pyproject.toml": _pyproject("requests>=2,<3"),
            "uv.lock": "version = 1\n",
        },
        {"pyproject.toml": _pyproject("requests>=2.31,<3"), "uv.lock": "version = 2\n"},
    )
    code, stdout, statuses, _ = _run_heavy(project, _stubs(tmp_path))
    assert code == 0, stdout
    assert statuses["76_lockfile"] == "pass"
    assert statuses["78_pins"] == "pass"
    assert "RESULT: PASS" in stdout


def test_no_lockfile_declared_is_noop_and_no_dependencies_is_noop(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "undeclared",
        {"borromeanrings.toml": _config(""), "pyproject.toml": _pyproject(None)},
        {"pyproject.toml": _pyproject(None) + "\n# touched\n"},
    )
    code, stdout, statuses, _ = _run_heavy(project, _stubs(tmp_path))
    assert code == 0, stdout
    assert statuses["76_lockfile"] == "noop"
    assert statuses["78_pins"] == "noop"
    # Honest about nothing: the gate says these two inspected nothing (ADR-0049).
    assert "inspected NOTHING" in stdout
    assert "76_lockfile" in stdout.split("inspected NOTHING", 1)[1]


def test_declared_lockfile_that_does_not_exist_fails_closed(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "missing",
        {"borromeanrings.toml": _config("uv.lock"), "pyproject.toml": _pyproject(None)},
        {"README.md": "docs only\n"},
    )
    code, stdout, statuses, receipts = _run_heavy(project, _stubs(tmp_path))
    assert code != 0, f"a declared-but-absent lockfile is a misconfiguration:\n{stdout}"
    assert statuses["76_lockfile"] == "fail"
    assert "does not exist" in (receipts / "76_lockfile.log").read_text(encoding="utf-8")


def test_git_failure_inside_a_repo_fails_closed(tmp_path: Path) -> None:
    project = _project(
        tmp_path / "brokenindex",
        {
            "borromeanrings.toml": _config("uv.lock"),
            "pyproject.toml": _pyproject(None),
            "uv.lock": "version = 1\n",
        },
        {"pyproject.toml": _pyproject(None) + "\n# touched\n"},
    )
    (project / ".git" / "index").write_text("GARBAGE-NOT-AN-INDEX", encoding="utf-8")
    code, stdout, statuses, receipts = _run_heavy(project, _stubs(tmp_path))
    assert code != 0, f"an undecidable git state must fail closed:\n{stdout}"
    assert statuses["76_lockfile"] == "fail"
    assert "failing closed" in (receipts / "76_lockfile.log").read_text(encoding="utf-8")
