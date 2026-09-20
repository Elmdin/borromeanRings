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


#: The Python half of the same mistake, inside the heredocs the scan above skips:
#:     out = subprocess.run(["git", …], capture_output=True).stdout
#: `.stdout` straight off the call is empty when git FAILED, exactly as it is when git
#: found nothing. The safe form keeps the result and reads `.returncode`, or uses
#: `meta_harness.git_read`, which raises (#186, ADR-0088).
PYTHON_GIT_STDOUT = re.compile(
    r"subprocess\.run\((?:[^()]|\([^()]*\))*\)\s*\.(stdout|stderr)", re.S
)

#: The same thing written over two lines — `done = subprocess.run(…)` and `done.stdout`
#: later — which is the most natural way to reintroduce the bug and which the chained
#: pattern above does not see (review of #260). Flagged unless that name's
#: `.returncode` is read somewhere.
PYTHON_GIT_ASSIGN = re.compile(
    r"(?P<name>\w+)\s*=\s*subprocess\.run\((?:[^()]|\([^()]*\))*\)", re.S
)

#: The scan reads SYNTAX, not intent: `if done.returncode == 0: pass` satisfies it while
#: doing nothing, and no regex settles that. What it does catch is the status never being
#: looked at, which is the accident this issue is about.
#:
#: What this scan does NOT see, stated rather than implied: a helper that wraps
#: `subprocess.run` and returns the result, and a comprehension that binds several of
#: them. Both are invisible to a regex over the call site, and the threat model here is
#: the same as the other text scans in this suite — an ACCIDENTAL regression by a
#: harness author, not an author working around the scan. A check written that way is a
#: code-review problem, and `15_a11y`'s `_git()` helper is the legitimate version of the
#: first shape (its callers read `.returncode`). Recorded so the next reader knows the
#: edge is chosen, not missed (review of #260).

#: Ways of running a command that DISCARD the status outright: `os.popen` (status only
#: via `.close()`, which nobody reads) and `Popen(...).communicate()` (status only via
#: `.returncode` afterwards). `subprocess.check_output` is NOT here: it raises on a
#: non-zero exit, which is the behaviour this whole issue is about.
PYTHON_STATUSLESS = re.compile(r"\bos\.popen\(|\.communicate\(")


def _python_in_heredocs(text: str) -> str:
    """The inverse of :func:`_shell_only`: only the embedded Python, lines preserved."""
    out: list[str] = []
    terminator: str | None = None
    for line in text.splitlines():
        if terminator is None:
            out.append("")
            match = HEREDOC.search(line)
            if match:
                terminator = match.group(1)
        elif line.strip() == terminator:
            out.append("")
            terminator = None
        else:
            out.append(line)
    return "\n".join(out)


def _inert(python: str, position: int, name: str) -> bool:
    """Is this mention of `<name>.returncode` one that cannot affect anything?

    Two shapes, both real decoys that silenced an earlier version of this scan: the
    status as a bare statement of its own, and the status unpacked into a name beside
    `.stdout` and then ignored.
    """
    _, line = _line_at(python, position)
    stripped = line.strip()
    if stripped == f"{name}.returncode":
        return True
    return bool(re.match(rf"^\w+\s*,\s*\w+\s*=\s*{re.escape(name)}\.returncode\s*,", stripped))


def _python_git_offenders(python: str) -> list[tuple[int, str]]:
    """Git read from Python whose exit status nobody reads."""
    found: list[tuple[int, str]] = [
        _line_at(python, match.start())
        for match in PYTHON_GIT_STDOUT.finditer(python)
        if '"git"' in match.group(0) or "'git'" in match.group(0)
    ]
    for match in PYTHON_GIT_ASSIGN.finditer(python):
        call = match.group(0)
        if '"git"' not in call and "'git'" not in call:
            continue
        name = match.group("name")
        # Does anything actually DO something with the status? Read the other way
        # round — every mention is taken as a real check unless it is one of the two
        # inert shapes, a bare statement or an unused tuple-unpack — because the first
        # attempt (a keyword-or-operator regex) rejected `rc = done.returncode` followed
        # by `if rc != 0: raise`, which is correct code, while still passing
        # `if done.returncode == 0: pass`, which does nothing (review of #260).
        mentions = list(re.finditer(rf"\b{re.escape(name)}\.returncode\b", python))
        if any(not _inert(python, at.start(), name) for at in mentions):
            continue  # the status IS read — the safe form
        if re.search(rf"\b{re.escape(name)}\.(stdout|stderr)\b", python) or re.search(
            rf"getattr\(\s*{re.escape(name)}\s*,", python
        ):
            found.append(_line_at(python, match.start()))
    for match in PYTHON_STATUSLESS.finditer(python):
        number, line = _line_at(python, match.start())
        if "git" in line:
            found.append((number, line))
    return sorted({(number, line.strip()) for number, line in found})


def test_no_check_reads_git_from_python_without_reading_its_status() -> None:
    """`74_secret_history` printed "empty history — nothing to scan" and exited 0 over a
    history it could not read, because `.stdout` is empty either way."""
    offenders: list[str] = []
    for script in _scripts():
        python = _python_in_heredocs(script.read_text(encoding="utf-8"))
        for number, line in _python_git_offenders(python):
            offenders.append(f"{script.relative_to(CHECKS)}:{number}: {line}")
    assert not offenders, (
        "a git subprocess whose status nobody reads (#186):\n"
        + "\n".join(offenders)
        + "\nUse meta_harness.git_read, which raises GitUnavailable."
    )


def test_every_way_of_ignoring_a_git_subprocess_status_is_flagged() -> None:
    """The chained form was all the first version saw; these are the rewrites that
    reintroduce the same bug (review of #260)."""
    for swallowed in (
        'x = subprocess.run(["git", "-C", root, "log"], capture_output=True).stdout',
        'done = subprocess.run(["git", "log"], capture_output=True)\nout = done.stdout',
        'done = subprocess.run(["git", "log"])\nout = getattr(done, "stdout")',
        'out = os.popen("git log").read()',
        'out, _ = subprocess.Popen(["git", "log"]).communicate()',
    ):
        assert _python_git_offenders(swallowed), swallowed


def test_a_decoy_mention_of_the_status_does_not_silence_the_scan() -> None:
    """An earlier version accepted the substring appearing anywhere in the file."""
    for decoy in (
        'done = subprocess.run(["git", "log"], capture_output=True)\n'
        "done.returncode\nout = done.stdout",
        'done = subprocess.run(["git", "log"], capture_output=True)\n'
        "code, out = done.returncode, done.stdout",
    ):
        assert _python_git_offenders(decoy), decoy


def test_reading_the_status_is_not_flagged() -> None:
    """The form 15_a11y and 16_shellcheck already use, and the one that raises."""
    for safe in (
        'done = subprocess.run(["git", "log"], capture_output=True)\n'
        "if done.returncode != 0:\n    fail()\nout = done.stdout",
        'out = subprocess.check_output(["git", "log"])  # raises on a non-zero exit',
        'out = git_text(root, "log")',
    ):
        assert _python_git_offenders(safe) == [], safe


def test_the_python_scan_reads_only_the_heredocs_the_shell_scan_skips() -> None:
    """The two halves partition the file between them: neither double-reports."""
    bad = 'x = subprocess.run(["git", "-C", root, "log"], capture_output=True).stdout\n'
    wrapped = "cmd <<'PY'\n" + bad + "PY\n"

    assert _python_git_offenders(_python_in_heredocs(wrapped))
    assert _swallowed(wrapped) == [], "the shell scan must not double-report it"


def test_the_status_read_through_another_name_is_not_a_false_positive() -> None:
    """Correct code, and the shape a keyword-anchored regex rejected: the status is
    taken into a name first and the branch happens on that (review of #260)."""
    safe = (
        'done = subprocess.run(["git", "log"], capture_output=True)\n'
        "rc = done.returncode\n"
        "if rc != 0:\n    raise RuntimeError(done.stderr)\n"
        "out = done.stdout"
    )

    assert _python_git_offenders(safe) == []
