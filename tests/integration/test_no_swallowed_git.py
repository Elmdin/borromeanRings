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

#: A git call inside a capture, spanning however many lines the author wrote it over —
#: a call split across lines evaded the first version of this scan (review of #258).
CAPTURE = re.compile(r"\$\((?:[^()]|\n)*?\bgit\b(?:[^()]|\n)*?\)", re.S)

#: Forms that DO read the status, and are what a converted site looks like:
#:   if ! x="$(git …)"; then …            — the status decides the branch
#:   x="$(git …)" || borromeanrings_…     — the status decides what happens next
#: `|| true`, `|| :` and `|| echo …` are NOT among them: they discard it by design.
#: Everything else is flagged. An earlier version only looked for the two literal
#: suppression idioms, so a plain `x="$(git …)"` whose `$?` nobody reads — the most
#: ordinary way to regress — passed straight through (review of #258).
GUARDED = re.compile(r"\b(el)?if\s+!")
HANDLED = re.compile(r"\|\|\s*(?!true\b|:\s|echo\b)\S")

#: Lines not yet converted, each with why it is still there. Keyed by the line's own
#: text, NOT by file: one legitimate exemption must not excuse every other swallowed git
#: call in the same script (review of #258). Remove an entry when the line converts;
#: never add one for new code (#186 tracks the remainder).
KNOWN: tuple[tuple[str, str, str], ...] = (
    (
        "shared/06_git_identity.sh",
        "rev-parse --is-inside-work-tree",
        "git reports an unusable repository and no repository identically here, and "
        "both end in noop (ADR-0087).",
    ),
    (
        "shared/08_branch.sh",
        "rev-parse --abbrev-ref --symbolic-full-name",
        "'no upstream' is the documented answer for this probe, not a failure.",
    ),
    (
        "shared/08_branch.sh",
        "rev-list --count",
        "reached only with an upstream that exists; an unknown count is the "
        "documented 'cannot judge' answer (the check's own header).",
    ),
    (
        "shared/25_provenance.sh",
        "rev-parse --show-prefix",
        "a failure means no repository, and this check's git errors are already "
        "threaded to its Python side.",
    ),
    (
        "python/17_prior_art.sh",
        "rev-parse --show-prefix",
        "same as 25_provenance.",
    ),
)


def _exempt(rel: str, line: str) -> bool:
    return any(rel == known_rel and snippet in line for known_rel, snippet, _ in KNOWN)


def _scripts() -> list[Path]:
    return sorted(p for p in CHECKS.rglob("*.sh") if p.name != "_lib.sh")


def test_the_known_list_describes_real_files() -> None:
    """A stale entry would silently license a converted site to regress."""
    for rel, _, _ in KNOWN:
        assert (CHECKS / rel).is_file(), f"{rel} is on the known list but does not exist"


def _swallowed(text: str) -> list[tuple[int, str]]:
    """(line number, line) for every git capture whose exit status nobody reads."""
    found: list[tuple[int, str]] = []
    for match in CAPTURE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        # The whole statement: the capture may end lines below where it started, and the
        # `|| handler` that reads its status comes after it.
        stmt_end = text.find("\n", match.end())
        statement = text[line_start : stmt_end if stmt_end != -1 else len(text)]
        if GUARDED.search(statement) or HANDLED.search(statement[match.end() - line_start :]):
            continue
        line_end = text.find("\n", match.start())
        line = text[line_start : line_end if line_end != -1 else len(text)]
        found.append((text.count("\n", 0, match.start()) + 1, line.strip()))
    return found


def test_no_new_check_swallows_a_git_failure() -> None:
    offenders: list[str] = []
    for script in _scripts():
        rel = str(script.relative_to(CHECKS))
        for number, line in _swallowed(script.read_text(encoding="utf-8")):
            if not _exempt(rel, line):
                offenders.append(f"{rel}:{number}: {line}")
    assert not offenders, (
        "a git call whose failure is discarded, feeding a verdict (#186):\n"
        + "\n".join(offenders)
        + "\nUse borromeanrings_git_capture + borromeanrings_cannot_read."
    )


def test_a_form_that_reads_the_status_is_not_flagged() -> None:
    """Both shapes a converted site uses. Flagging them would train the next author to
    ignore this scan."""
    guarded = 'if ! merge_base="$(git -C "$ROOT" merge-base HEAD "$base" 2>/dev/null)"; then'
    handled = 'changed="$(git -C "$ROOT" diff --name-only HEAD)" || borromeanrings_cannot_read x'

    assert _swallowed(guarded) == []
    assert _swallowed(handled) == []


def test_every_way_of_not_reading_the_status_is_flagged() -> None:
    """The scan used to look only for `|| true` and `2>/dev/null`, so the most ordinary
    regression — a capture whose `$?` nobody ever reads — went unnoticed, and `|| :`
    walked past it too (review of #258)."""
    for swallowed in (
        'x="$(git log --format=%s 2>/dev/null || true)"',
        'x="$(git log --format=%s || :)"',
        'x="$(git log --format=%s)"',  # nothing suppressed, nothing read either
        'x="$(git log --format=%s 2>"$err")"',
        'x="$(git rev-parse HEAD 2>/dev/null || echo HEAD)"',
    ):
        assert _swallowed(swallowed), swallowed


def test_a_call_split_across_lines_is_still_seen() -> None:
    """The first version of this scan was per-line, so an author who wrapped the call
    slipped past it (review of #258)."""
    wrapped = (
        'remote_ref="$(git -C "$ROOT" rev-parse --abbrev-ref \\\n'
        '  "$b@{upstream}" 2>/dev/null || true)"'
    )

    assert _swallowed(wrapped)


def test_every_known_site_is_still_one() -> None:
    """The list only shrinks. An entry whose file no longer has the pattern is removed
    here, not left behind to excuse the next one."""
    stale = []
    for rel, snippet, _ in KNOWN:
        found = _swallowed((CHECKS / rel).read_text(encoding="utf-8"))
        if not any(snippet in line for _, line in found):
            stale.append(f"{rel}: {snippet}")
    assert not stale, f"converted — remove from KNOWN: {stale}"
