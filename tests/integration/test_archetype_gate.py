"""End-to-end: the archetype dimension through the real gate (SPEC-archetypes.md).

Four outcomes must stay distinct, and the last is the one this feature exists for:

* **off** — no ``[project].archetypes`` ⇒ ``21_archetype`` is ``noop`` and the run passes
  exactly as before the feature existed (back-compat).
* **complete** — every required feature present ⇒ ``pass``.
* **incomplete** — one required feature absent ⇒ ``fail``, naming it.
* **hollow green turned red** — a declared ``web-app`` whose ``15_a11y`` inspected no HTML:
  every receipt is non-failing, yet the run is FAIL because the archetype requires that
  check to have inspected something (ADR-0062 / the #130 vacuity case).

See ADR-0049 for why ``noop`` alone is non-failing, and ADR-0062 for the override.
"""

import json
import os
import subprocess
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
VERIFY = BORROMEANRINGS_HOME / "verify.sh"
GATE_TIMEOUT_S = 180

# language "c" selects no per-language check set, so only the shared checks in
# [checks].required run — the fixtures exercise the archetype rule in isolation.
EMBEDDED_FILES = {
    ".clang-tidy": "Checks: '-*,misra-*'\n",
    "hal/gpio.h": "void gpio_init(void);\n",
    "firmware/main.c": '#include "hal/gpio.h"\nvoid kick(void) { IWDG->KR = 0xAAAA; }\n',
    "link.ld": "MEMORY { FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 64K }\n",
    "tests/test_host.c": "int main(void) { return 0; }\n",
    "platformio.ini": "[env:board]\nplatform = ststm32\n",
}


def _config(archetypes: str, required: str, language: str = "c") -> str:
    return (
        f'[project]\nlanguage = "{language}"\nsrc_dir = "src"\n{archetypes}\n'
        f"[checks]\nrequired = [{required}]\n\n[hygiene]\nrequires = []\n"
    )


def _run_gate(project: Path) -> tuple[int, str, dict[str, str]]:
    """Run the real gate against ``project``; return (exit, stdout, {check: status})."""
    env = dict(os.environ)
    env["BORROMEANRINGS_PROJECT"] = str(project)
    proc = subprocess.run(
        ["bash", str(VERIFY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_S,
    )
    statuses: dict[str, str] = {}
    run_dirs = sorted(p for p in (project / ".meta-harness" / "receipts").glob("*") if p.is_dir())
    if run_dirs:
        for receipt in run_dirs[-1].glob("*.json"):
            statuses[receipt.stem] = json.loads(receipt.read_text()).get("status", "?")
    return proc.returncode, proc.stdout, statuses


def _git_project(root: Path, files: dict[str, str]) -> Path:
    """Materialize a real git repo (15_a11y lists tracked HTML via git)."""
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


def _check_log(project: Path, check: str) -> str:
    return next((project / ".meta-harness" / "receipts").glob(f"*/{check}.log")).read_text()


def test_no_archetypes_declared_is_off_and_green(tmp_path: Path) -> None:
    """Back-compat: a project that never heard of archetypes gates exactly as before."""
    project = _git_project(tmp_path / "off", {"borromeanrings.toml": _config("", '"21_archetype"')})
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("21_archetype") == "noop"
    assert "ARCHETYPE:" not in stdout
    assert "rule off" in _check_log(project, "21_archetype")


def test_complete_archetype_passes_with_evidence(tmp_path: Path) -> None:
    files = dict(EMBEDDED_FILES)
    files["borromeanrings.toml"] = _config('archetypes = ["embedded"]', '"21_archetype"')
    project = _git_project(tmp_path / "complete", files)
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("21_archetype") == "pass"
    log = _check_log(project, "21_archetype")
    assert "all 6 required feature(s) present" in log
    assert "[firmware/main.c:2]" in log  # evidence, not just a verdict


def test_missing_required_feature_fails_naming_it(tmp_path: Path) -> None:
    files = {k: v for k, v in EMBEDDED_FILES.items() if k != "link.ld"}
    files["borromeanrings.toml"] = _config('archetypes = ["embedded"]', '"21_archetype"')
    project = _git_project(tmp_path / "incomplete", files)
    code, stdout, statuses = _run_gate(project)
    assert code != 0, f"an absent required feature must fail the gate:\n{stdout}"
    assert statuses.get("21_archetype") == "fail"
    log = _check_log(project, "21_archetype")
    assert "MISSING  linker_script_present" in log
    assert "- linker_script_present:" in log


def test_unknown_archetype_fails_closed_before_any_check_runs(tmp_path: Path) -> None:
    project = _git_project(
        tmp_path / "unknown",
        {"borromeanrings.toml": _config('archetypes = ["firmware"]', '"21_archetype"')},
    )
    code, stdout, statuses = _run_gate(project)
    assert code != 0
    assert statuses == {}  # the config is refused, so no receipt is ever written


WEB_APP_FILES = {
    "locales/en.json": '{"hello": "Hello"}\n',
    "templates/base.jinja": '<meta name="viewport" content="width=device-width">\n',
    "budget.json": "[]\n",
    "src/error.tsx": "export const ErrorBoundary = () => null;\n",
    "src/log.py": "import structlog\n",
    "tests/test_log.py": "def test_ok() -> None:\n    assert True\n",
}
WEB_APP_CONFIG = _config(
    'archetypes = ["web-app"]', '"21_archetype", "15_a11y", "40_test"', language="python"
)


def test_archetype_turns_a_hollow_green_red(tmp_path: Path) -> None:
    """Every receipt non-failing, yet FAIL: the declared web app has no HTML for 15_a11y."""
    files = dict(WEB_APP_FILES)
    files["borromeanrings.toml"] = WEB_APP_CONFIG
    project = _git_project(tmp_path / "hollow", files)
    code, stdout, statuses = _run_gate(project)
    required = {k: statuses.get(k) for k in ("21_archetype", "15_a11y", "40_test")}
    assert required == {"21_archetype": "pass", "15_a11y": "noop", "40_test": "pass"}
    assert code != 0, f"a noop the archetype forbids must FAIL the run:\n{stdout}"
    assert "15_a11y: NOOP but required to inspect something by archetype web-app" in stdout
    assert "RESULT: FAIL" in stdout


def test_same_web_app_with_html_passes_for_the_right_reason(tmp_path: Path) -> None:
    """Negative control: once 15_a11y has something to inspect, the run is green."""
    files = dict(WEB_APP_FILES)
    files["borromeanrings.toml"] = WEB_APP_CONFIG
    files["index.html"] = "<html lang='en'><head><title>App</title></head><body></body></html>\n"
    project = _git_project(tmp_path / "real", files)
    code, stdout, statuses = _run_gate(project)
    assert code == 0, stdout
    assert statuses.get("15_a11y") == "pass"
    assert "ARCHETYPE:" not in stdout
