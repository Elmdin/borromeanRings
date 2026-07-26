"""The provider-agnostic critic judge (scripts/critic-judge.sh) is fail-closed:
with no model provider it answers 'no', so a missing/broken judge can never
silently pass a gate. The live provider paths need credentials and are exercised
only when activated. See docs/CRITIC-ACTIVATION.md and ADR-0030/0036."""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "critic-judge.sh"


def test_no_provider_is_fail_closed() -> None:
    # Minimal env: ANTHROPIC_API_KEY unset (env -i clears it) and a PATH without the
    # `claude` CLI, so neither provider is available → the fail-closed 'no' path.
    result = subprocess.run(
        ["env", "-i", "PATH=/usr/bin:/bin", "bash", str(SCRIPT)],
        input="Is this docstring accurate? ARTIFACT: def f(): return 1",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.stdout.strip().lower().startswith("no")
