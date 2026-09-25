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

#: A git call inside a `$( … )` capture, spanning however many lines the author wrote it
#: over — a call split across lines evaded the first version of this scan (review of
#: #258). Whether its status is read is decided below. `[^()]` already matches a
#: newline: spelling it `(?:[^()]|\n)` as well made the pattern ambiguous, and the scan
#: hung on the first long line it met.
CAPTURE = re.compile(r"\$\([^()]*?\bgit\b[^()]*?\)", re.S)

#: Captures that LOSE git's status entirely, so there is nothing a caller could read:
#: backticks (same as `$( … )`, older spelling), process substitution into `read` or
#: `mapfile` (`$?` there is the READER's status, not git's), and a pipe into either.
#: These are always flagged — a careful author checking `$?` would still be fooled.
STATUSLESS = (
    re.compile(r"`[^`]*\bgit\b[^`]*`"),
    re.compile(r"<\(\s*[^()]*?\bgit\b[^()]*?\)", re.S),
    re.compile(r"\bgit\b[^|\n]*\|\s*(read|mapfile)\b"),
)

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


HEREDOC = re.compile(r"<<-?\s*[\'\"]?([A-Za-z_][A-Za-z0-9_]*)[\'\"]?")


def _shell_only(text: str) -> str:
    """``text`` with heredoc bodies blanked, line numbers preserved.

    Every check embeds Python in a heredoc, and that Python is not shell: its own git
    calls are the Python-side half of #186, which needs a Python helper and a different
    scan. Reading them here would flag a Python print that merely quotes a git
    command in its message as a swallowed call (review of #258).
    """
    out: list[str] = []
    terminator: str | None = None
    for line in text.splitlines():
        if terminator is None:
            out.append(line)
            match = HEREDOC.search(line)
            if match:
                terminator = match.group(1)
        else:
            out.append("")
            if line.strip() == terminator:
                terminator = None
    return "\n".join(out)


def _is_comment(line: str) -> bool:
    """A shell comment cannot run. These scripts document themselves at length, and
    backticks are also how prose quotes a command — `git config user.*` in a header is
    not a call (review of #258)."""
    return line.lstrip().startswith("#")


def _line_at(text: str, position: int) -> tuple[int, str]:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    return text.count("\n", 0, position) + 1, text[start : end if end != -1 else len(text)]


def _swallowed(source: str) -> list[tuple[int, str]]:
    """(line number, line) for every git call whose exit status nobody reads."""
    text = _shell_only(source)
    found: list[tuple[int, str]] = []
    for match in CAPTURE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        # The whole statement: the capture may end lines below where it started, and the
        # `|| handler` that reads its status comes after it.
        stmt_end = text.find("\n", match.end())
        statement = text[line_start : stmt_end if stmt_end != -1 else len(text)]
        if GUARDED.search(statement) or HANDLED.search(statement[match.end() - line_start :]):
            continue
        number, line = _line_at(text, match.start())
        if not _is_comment(line):
            found.append((number, line.strip()))
    for pattern in STATUSLESS:
        for match in pattern.finditer(text):
            number, line = _line_at(text, match.start())
            if not _is_comment(line):
                found.append((number, line.strip()))
    return sorted(set(found))


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


def test_python_inside_a_heredoc_is_not_shell() -> None:
    """Every check embeds Python in a heredoc. Its git calls are the Python-side half of
    #186 — a different helper and a different scan — and its prose is not a call."""
    embedded = (
        "borromeanrings_py - <<'PY'\nprint(\"git is present but `git ls-files` failed\")\nPY\n"
    )

    assert _swallowed(embedded) == []


def test_prose_in_a_comment_is_not_a_call() -> None:
    """These scripts explain themselves at length, and backticks are how prose quotes a
    command. Flagging a header comment would make the scan noise."""
    assert _swallowed("# the repo's transient `git config user.*` is the guard's concern") == []
    assert _swallowed("  # x=`git log` would be wrong") == []


def test_a_capture_that_loses_the_status_entirely_is_flagged() -> None:
    """Worse than the original bug: after these, `$?` is the reader's status, not git's,
    so even an author who checks it is told the wrong thing (review of #258). None of
    them is in the tree today; the scan is what keeps it that way."""
    for statusless in (
        "x=`git log --format=%s`",
        "mapfile -t lines < <(git log --format=%s)",
        "read -r first < <(git log --format=%s)",
        "git log --format=%s | read -r first",
    ):
        assert _swallowed(statusless), statusless


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


#: Ratchet baselines read with `cat <file> 2>/dev/null || echo <permissive>`: absent and
#: unreadable collapse into "the most permissive value", so the ratchet switches itself
#: off without saying so. #186 built `borromeanrings_baseline` for exactly this line and
#: converted the three python ratchets; go, typescript and the mutation lane were left
#: behind and found by the audit of 2026-09-20.
BASELINE_CAT = re.compile(r'baseline="\$\(\s*cat[^)]*\)"')


def test_no_check_reads_a_ratchet_baseline_by_hand() -> None:
    offenders: list[str] = []
    for script in _scripts():
        text = _shell_only(script.read_text(encoding="utf-8"))
        for match in BASELINE_CAT.finditer(text):
            number, line = _line_at(text, match.start())
            if not _is_comment(line):
                offenders.append(f"{script.relative_to(CHECKS)}:{number}: {line.strip()}")
    assert not offenders, (
        "a baseline read that cannot tell absent from unreadable (#186):\n"
        + "\n".join(offenders)
        + "\nUse borromeanrings_baseline."
    )


def test_every_ratchet_check_uses_the_shared_baseline_reader() -> None:
    """The positive half: a check that HAS a baseline file must read it through the
    helper, so a new lane cannot quietly hand-roll the comparison again."""
    missing: list[str] = []
    for script in _scripts():
        text = script.read_text(encoding="utf-8")
        if "baseline_file=" not in text:
            continue
        if "borromeanrings_baseline" not in text:
            missing.append(str(script.relative_to(CHECKS)))
    assert not missing, f"declares a baseline file but does not use the shared reader: {missing}"
