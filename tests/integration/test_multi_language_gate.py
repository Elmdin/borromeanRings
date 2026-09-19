"""End-to-end: the TypeScript and Go lanes run under the real gate (SPEC-multi-language.md).

Two things must hold whatever is installed on the machine running this suite:

* **Tools absent** — every lane check reports ``noop`` and names its tool
  (``<tool> not installed``); the gate is green; the output says
  ``inspected NOTHING: 6 of 6``. Absence is made deterministic by running the gate with a
  sandboxed ``PATH`` holding only the binaries the gate itself needs, so a developer with
  Go installed gets the same result as CI without it. Nothing is ever installed.
* **Unknown language** — the gate refuses to run rather than defaulting to Python.

Positive cases (a tool really runs) execute only when that tool is present on this
machine; they are skipped otherwise and say so.

Excluded from mutmut (setup.cfg): drives bash, not Python.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 180
LANE_CHECKS = ("00_build", "10_format", "20_lint", "30_typecheck", "40_test", "50_security")

# What each lane check names when its tool is missing (the SPEC's exact wording).
TS_TOOLS = {
    "00_build": "tsc not installed",
    "10_format": "prettier not installed",
    "20_lint": "eslint not installed",
    "30_typecheck": "tsc not installed",
    "40_test": "vitest not installed; jest not installed",
    "50_security": "ast-grep not installed",
}
GO_TOOLS = {
    "00_build": "go not installed",
    "10_format": "gofmt not installed",
    "20_lint": "go not installed",
    "30_typecheck": "staticcheck not installed",
    "40_test": "go not installed",
    "50_security": "gosec not installed",
}

# Binaries the gate itself needs; everything else (go, node, tsc, ...) is hidden.
GATE_BINARIES = (
    "bash",
    "git",
    "timeout",
    "date",
    "mkdir",
    "find",
    "cat",
    "rm",
    "printf",
    "head",
    "tail",
    "sort",
    "wc",
    "dirname",
    "basename",
    "tr",
    "sed",
    "grep",
    "env",
    "uname",
    "readlink",
    "ls",
    "cp",
    "mv",
    "touch",
    "mktemp",
    "sh",
)


def _config(language: str) -> str:
    required = ", ".join(f'"{c}"' for c in LANE_CHECKS)
    return (
        f'[project]\nlanguage = "{language}"\nsrc_dir = "src"\n\n'
        f"[checks]\nrequired = [{required}]\n\n[hygiene]\nrequires = []\n"
    )


TS_PROJECT = {
    "borromeanrings.toml": _config("typescript"),
    "package.json": '{"name": "fixture-ts", "private": true, "version": "0.0.0"}\n',
    "tsconfig.json": '{"compilerOptions": {"strict": true, "noEmit": true}, "include": ["src"]}\n',
    "src/index.ts": "export function add(a: number, b: number): number {\n  return a + b;\n}\n",
}
GO_PROJECT = {
    "borromeanrings.toml": _config("go"),
    "go.mod": "module example.com/fixture\n\ngo 1.21\n",
    "src/add.go": "package src\n\n// Add returns a + b.\nfunc Add(a, b int) int { return a + b }\n",
    "src/add_test.go": (
        'package src\n\nimport "testing"\n\n'
        'func TestAdd(t *testing.T) {\n\tif Add(1, 2) != 3 {\n\t\tt.Fatal("bad")\n\t}\n}\n'
    ),
}


def _sandbox_path(tmp_path: Path) -> str:
    """A PATH holding only the gate's own binaries — every lane tool is absent."""
    bin_dir = tmp_path / "sandbox-bin"
    bin_dir.mkdir()
    for name in GATE_BINARIES:
        real = shutil.which(name)
        if real:
            (bin_dir / name).symlink_to(real)
    (bin_dir / "python3").symlink_to(sys.executable)
    return str(bin_dir)


def _run_gate(project: Path, *, path: str | None = None) -> tuple[int, str, dict[str, str]]:
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    if path is not None:
        env["PATH"] = path
    proc = subprocess.run(
        ["bash", str(VERIFY)], env=env, capture_output=True, text=True, timeout=GATE_TIMEOUT_S
    )
    statuses: dict[str, str] = {}
    run_dirs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    if run_dirs:
        for receipt in run_dirs[-1].glob("*.json"):
            statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
    return proc.returncode, proc.stdout + proc.stderr, statuses


def _log(project: Path, check: str) -> str:
    return next((project / ".meta-harness" / "receipts").glob(f"*/{check}.log")).read_text()


def _git_project(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    for argv in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
    ):
        subprocess.run(argv, cwd=root, capture_output=True, check=False)
    return root


@pytest.mark.parametrize(
    ("language", "files", "tools"),
    [("typescript", TS_PROJECT, TS_TOOLS), ("go", GO_PROJECT, GO_TOOLS)],
    ids=["typescript", "go"],
)
def test_lane_without_tools_is_green_and_honest(
    tmp_path: Path, language: str, files: dict[str, str], tools: dict[str, str]
) -> None:
    """Every lane check noops naming its tool; nothing is installed; the green says so."""
    project = _git_project(tmp_path / language, files)
    code, out, statuses = _run_gate(project, path=_sandbox_path(tmp_path))
    assert code == 0, out
    assert {c: statuses.get(c) for c in LANE_CHECKS} == dict.fromkeys(LANE_CHECKS, "noop")
    for check, expected in tools.items():
        assert expected in _log(project, check), check
    assert "inspected NOTHING: 6 of 6" in out
    assert "RESULT: PASS" in out
    assert not (project / "node_modules").exists()


def test_greenfield_lane_project_is_noop_before_tools_are_consulted(tmp_path: Path) -> None:
    """No source of the language ⇒ noop for the greenfield reason, whatever is installed."""
    project = _git_project(tmp_path / "gf", {"borromeanrings.toml": _config("go")})
    code, out, statuses = _run_gate(project)
    assert code == 0, out
    assert all(statuses.get(c) == "noop" for c in LANE_CHECKS), statuses
    assert "no Go source in 'src' yet (greenfield)" in _log(project, "00_build")


def test_unknown_language_fails_closed(tmp_path: Path) -> None:
    """A language with no lane must not fall through to Python's checks."""
    project = _git_project(tmp_path / "rust", {"borromeanrings.toml": _config("rust")})
    code, out, statuses = _run_gate(project)
    assert code != 0, out
    assert "rust" in out and "cannot load" in out
    assert statuses == {}  # no lane ran at all


def test_vendored_typescript_does_not_count_as_source(tmp_path: Path) -> None:
    """node_modules under src_dir is not the project's code: still greenfield ⇒ noop."""
    project = _git_project(
        tmp_path / "vendored",
        {
            "borromeanrings.toml": _config("typescript"),
            "src/node_modules/dep/index.ts": "export const x = 1;\n",
        },
    )
    code, out, statuses = _run_gate(project, path=_sandbox_path(tmp_path))
    assert code == 0, out
    assert "greenfield" in _log(project, "00_build")


# --- Positive cases: only when the tool is really present on this machine -------------

_GO = shutil.which("go")


@pytest.mark.skipif(_GO is None, reason="go not installed on this machine")
def test_go_lane_builds_and_tests_a_real_module(tmp_path: Path) -> None:
    """With Go present, 00_build/20_lint/40_test do real work and pass; coverage is recorded."""
    project = _git_project(tmp_path / "go-real", GO_PROJECT)
    code, out, statuses = _run_gate(project)
    assert code == 0, out
    assert statuses["00_build"] == "pass" and statuses["20_lint"] == "pass"
    assert statuses["40_test"] == "pass"
    receipt = json.loads(
        next((project / ".meta-harness/receipts").glob("*/40_test.json")).read_text()
    )
    assert receipt["coverage_percent"] == 100.0


@pytest.mark.skipif(_GO is None, reason="go not installed on this machine")
def test_go_lane_fails_on_coverage_regression(tmp_path: Path) -> None:
    project = _git_project(tmp_path / "go-regress", GO_PROJECT)
    (project / ".borromeanrings-coverage-baseline").write_text("100.5\n")
    code, out, statuses = _run_gate(project)
    assert code != 0
    assert statuses["40_test"] == "fail"
    assert "COVERAGE REGRESSION" in _log(project, "40_test")


_TSC = shutil.which("tsc")
_AST_GREP = shutil.which("ast-grep")


@pytest.mark.skipif(_TSC is None, reason="tsc not installed on this machine")
def test_typescript_lane_compiles_a_real_project(tmp_path: Path) -> None:
    """With tsc present, 00_build/30_typecheck do real work; a type error fails closed."""
    project = _git_project(tmp_path / "ts-real", TS_PROJECT)
    code, out, statuses = _run_gate(project)
    assert code == 0, out
    assert statuses["00_build"] == "pass" and statuses["30_typecheck"] == "pass"
    broken = dict(TS_PROJECT, **{"src/index.ts": "export const n: number = 'not a number';\n"})
    project = _git_project(tmp_path / "ts-broken", broken)
    code, out, statuses = _run_gate(project)
    assert code != 0
    assert statuses["00_build"] == "fail"


@pytest.mark.skipif(_AST_GREP is None, reason="ast-grep not installed on this machine")
def test_typescript_security_finds_eval_and_names_the_site(tmp_path: Path) -> None:
    """With ast-grep present, 50_security passes clean source and fails on eval()."""
    project = _git_project(tmp_path / "ts-clean", TS_PROJECT)
    _, _, statuses = _run_gate(project)
    assert statuses["50_security"] == "pass"
    evil = dict(TS_PROJECT, **{"src/index.ts": "export const r = eval('1 + 1');\n"})
    project = _git_project(tmp_path / "ts-evil", evil)
    code, _, statuses = _run_gate(project)
    assert code != 0
    assert statuses["50_security"] == "fail"
    assert "src/index.ts:1 [no-eval]" in _log(project, "50_security")


# --- Stubbed ast-grep: the tool "present" path without installing anything ---------------

STUB_FINDING = (
    '[{"file": "src/index.ts", "range": {"start": {"line": 0, "column": 0}, '
    '"end": {"line": 0, "column": 4}}, "ruleId": "no-eval", "severity": "error", '
    '"message": "eval executes arbitrary code"}]'
)


def _stub_ast_grep(bin_dir: str, *, exit_code: int, stdout: str, stderr: str = "") -> None:
    """Write a shell script named ast-grep into the sandbox PATH — a stub, not an install."""
    stub = Path(bin_dir) / "ast-grep"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s' {stdout!r}\n"
        f"printf '%s' {stderr!r} >&2\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)


@pytest.mark.parametrize(
    ("exit_code", "stdout", "stderr", "expected", "in_log"),
    [
        (2, "", "Error: cannot parse rule file", "fail", "exited 2"),
        (0, "", "", "pass", "no findings"),
        (0, "[]", "", "pass", "no findings"),
        (0, STUB_FINDING, "", "fail", "src/index.ts:1 [no-eval]"),
        (1, STUB_FINDING, "Error: 1 error(s) found", "fail", "src/index.ts:1 [no-eval]"),
        (0, "garbage", "", "fail", "unreadable output"),
    ],
    ids=[
        "crash-empty-stdout",
        "clean-empty",
        "clean-array",
        "finding",
        "finding-nonzero",
        "garbage",
    ],
)
def test_typescript_security_consults_the_tool_exit_code(
    tmp_path: Path, exit_code: int, stdout: str, stderr: str, expected: str, in_log: str
) -> None:
    """A non-zero ast-grep exit is never a pass, whatever stdout parses to (PR #198 review)."""
    project = _git_project(tmp_path / "ts-stub", TS_PROJECT)
    path = _sandbox_path(tmp_path)
    _stub_ast_grep(path, exit_code=exit_code, stdout=stdout, stderr=stderr)
    code, out, statuses = _run_gate(project, path=path)
    assert statuses["50_security"] == expected, out
    assert (code == 0) == (expected == "pass")
    assert in_log in _log(project, "50_security")
