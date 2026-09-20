"""No check may swallow git's exit status and judge what it got anyway (#186).

The fail-OPEN shape, found in twelve places by the audit for #186:

    changed="$(git -C "$PROJECT_ROOT" diff --name-only "$base"...HEAD 2>/dev/null || true)"
    # ... verdict computed from $changed

A crashed git, a corrupt index or a missing object store each produce an empty string,
which reads as "nothing changed" — and the check reports a clean pass over a tree it
never read. `borromeanrings_git_capture` (checks/_lib.sh) is the replacement: it returns
git's real exit status and never hands back an empty answer with an empty error.

This test is the ratchet that keeps the pattern from coming back. Sites still on the old
shape are listed below with what each one is, so the list shrinks deliberately and is
never re-seeded: adding a NEW swallowed git call fails this test.
"""

from __future__ import annotations

import re
from pathlib import Path

BORROMEANRINGS_HOME = Path(__file__).resolve().parents[2]
CHECKS = BORROMEANRINGS_HOME / "checks"

#: A git call whose failure is discarded: `$( … git … || true )` or `2>/dev/null` inside
#: a capture. The helper is exempt — it is what a converted site calls.
SWALLOWED = re.compile(r"\$\([^)]*\bgit\b[^)]*(\|\|\s*true|2>\s*/dev/null)")

#: Sites not yet converted, each with why it is still here. Remove an entry when the
#: site converts; never add one for new code (#186 tracks the remainder).
KNOWN: dict[str, str] = {
    "shared/06_git_identity.sh": "`rev-parse --is-inside-work-tree || echo false`: git "
    "reports an unusable repository and no repository identically here, and both end "
    "in noop (ADR-0087).",
    "shared/08_branch.sh": "the upstream-ref probe: 'no upstream' is the documented "
    "answer, not a failure (its own header says so).",
    "shared/25_provenance.sh": "`rev-parse --show-prefix`: a failure means no "
    "repository, and the check's git errors are already threaded to Python.",
    "python/17_prior_art.sh": "`rev-parse --show-prefix`, same as 25_provenance.",
}


def _scripts() -> list[Path]:
    return sorted(p for p in CHECKS.rglob("*.sh") if p.name != "_lib.sh")


def test_the_known_list_describes_real_files() -> None:
    """A stale entry would silently license a converted site to regress."""
    for rel in KNOWN:
        assert (CHECKS / rel).is_file(), f"{rel} is on the known list but does not exist"


def test_no_new_check_swallows_a_git_failure() -> None:
    offenders: list[str] = []
    for script in _scripts():
        rel = str(script.relative_to(CHECKS))
        for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            if SWALLOWED.search(line) and rel not in KNOWN:
                offenders.append(f"{rel}:{number}: {line.strip()}")
    assert not offenders, (
        "a git call whose failure is discarded, feeding a verdict (#186):\n"
        + "\n".join(offenders)
        + "\nUse borromeanrings_git_capture + borromeanrings_cannot_read."
    )


def test_every_known_site_is_still_one() -> None:
    """The list only shrinks. An entry whose file no longer has the pattern is removed
    here, not left behind to excuse the next one."""
    stale = []
    for rel in KNOWN:
        text = (CHECKS / rel).read_text(encoding="utf-8")
        if not any(SWALLOWED.search(line) for line in text.splitlines()):
            stale.append(rel)
    assert not stale, f"converted — remove from KNOWN: {stale}"
