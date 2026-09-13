"""What a project gets by default from `init.sh`, exercised rather than assumed (#230).

A planted AWS secret access key passed the gate on a project set up by the real
`init.sh` — twice over. The pattern set did not cover it, and the default required
set did not include `12_secrets` at all, so even a covered credential would have
gone through. Both were invisible because every previous test wrote its own
`borromeanrings.toml` and therefore tested a config no new user ever gets.

These tests run the real `init.sh` and the real gate, and never write a config.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import tomllib

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
INIT = BORROMEANRINGS_HOME / "init.sh"
VERIFY = BORROMEANRINGS_HOME / "verify.sh"

# Built at runtime so this file's source carries no literal token.
_AWS_SECRET = "wJalrXUtnFEMI/" + "K7MDENG/bPxRfiCYEXAMPLEKEY"
_AWS_ID = "AKIA" + "1234567890ABCDEF"


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "fresh"
    (project / "src" / "demo").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1"\n')
    (project / "src" / "demo" / "__init__.py").write_text('"""demo."""\n')
    (project / "tests" / "test_ok.py").write_text('"""t."""\n\n\ndef test_ok():\n    assert True\n')
    subprocess.run(["git", "init", "-q", "."], cwd=project, check=False, timeout=60)
    result = subprocess.run(
        ["bash", str(INIT), str(project)], capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    return project


def _gate(project: Path) -> subprocess.CompletedProcess[str]:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@e.com", "add", "-A"],
        cwd=project,
        check=False,
        timeout=60,
    )
    return subprocess.run(
        ["bash", str(VERIFY)],
        env={**os.environ, "BORROMEANRINGS_PROJECT": str(project)},
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_the_default_required_set_gates_secrets(tmp_path: Path) -> None:
    """`12_secrets` costs nothing to pass on a clean project, so it is not a ratchet.

    The "start green" default is right for maturity checks — `[hygiene].requires`
    is empty for exactly that reason — but a secret check only ever fires when
    there really is a credential in the tree. Leaving it out traded no friction
    for no protection.
    """
    project = _project(tmp_path)
    config = tomllib.loads((project / "borromeanrings.toml").read_text(encoding="utf-8"))
    assert "12_secrets" in config["checks"]["required"]


def test_a_fresh_project_starts_green(tmp_path: Path) -> None:
    """Adding the check must not cost a new project its first green run."""
    assert "RESULT: PASS" in _gate(_project(tmp_path)).stdout


@pytest.mark.parametrize(
    ("label", "planted"),
    [
        ("aws-secret-access-key", f'AWS_SECRET_ACCESS_KEY = "{_AWS_SECRET}"'),
        ("aws-access-key-id", f'AWS_ACCESS_KEY_ID = "{_AWS_ID}"'),
    ],
)
def test_a_planted_credential_fails_a_default_project(
    tmp_path: Path, label: str, planted: str
) -> None:
    """The end-to-end claim: a credential in a governed project stops the gate.

    Asserted against a config the user actually receives, not one written by the
    test. The secret half is the one that grants access; the ID is the public half
    and was the only one covered.
    """
    project = _project(tmp_path)
    (project / "src" / "demo" / "creds.py").write_text(f'"""c."""\n\n{planted}\n', encoding="utf-8")

    result = _gate(project)

    assert "RESULT: FAIL" in result.stdout, f"{label} passed a default-configured project"
    assert "12_secrets" in result.stdout
