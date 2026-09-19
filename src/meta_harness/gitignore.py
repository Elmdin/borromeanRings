"""Make sure a governed project ignores borromeanRings' own output (#219).

borromeanRings writes receipts, verdicts and state under ``.meta-harness/``, and
``40_test`` runs pytest with ``--cov``, so coverage.py drops a ``.coverage`` data
file in the project too. This repository's own ``.gitignore`` has carried those
entries from the start; neither ``init.sh`` nor ``adopt.sh`` ever gave them to
anyone else. So every governed project
accumulated the harness's output as untracked, un-ignored files in its working
tree — and the gate's own writes became part of the state the gate examines.

That is not untidiness. Measured on a fresh project with no ``.gitignore``:
``12_secrets`` reads the git index, `git add -A` puts the receipt logs in it, and a
check log that quotes a secret-shaped line makes the secret gate fail **on the
harness's own output** — still failing after the offending source file is deleted,
pointing at generated files, telling the user to rotate a secret that no longer
exists.

The decision this module encodes, since adding a line to a file the project owns is
a real write:

* no ``.gitignore`` at all      → create it, with the entry and a comment saying why;
* present, entry absent         → append, and the caller says so on stdout;
* entry present in any spelling → do nothing (idempotent by path, not by line);
* the caller may skip entirely  → ``init.sh --no-gitignore`` / ``adopt.sh --no-gitignore``,
  the explicit escape hatch for a project that has decided it wants the receipts
  tracked. Explicit, rather than inferred from an absence we cannot read.

Pure decision + one narrow write, so the rules are unit-testable without a repo.
"""

from __future__ import annotations

from pathlib import Path

ENTRY = ".meta-harness/"
COMMENT = "# borromeanRings gate output — not project content"

# What a gate run leaves in the project, and nothing else. `.coverage` is here
# because 40_test runs pytest with --cov: coverage.py writes its data file into the
# working directory, so the project acquires it by being gated, not by choosing to
# measure coverage. `__pycache__/` is deliberately NOT here — a project gets that
# from running its own tests, and what it does about that is its business.
ARTEFACTS: tuple[str, ...] = (ENTRY, ".coverage")

# Every spelling git honours for one of the entries above. Matching on these rather
# than on the literal line keeps the write idempotent against a hand-edited file.
_EQUIVALENT = {
    ENTRY: frozenset({".meta-harness", ".meta-harness/", "/.meta-harness", "/.meta-harness/"}),
    ".coverage": frozenset({".coverage", "/.coverage", ".coverage*"}),
}


def _lines(gitignore_text: str) -> list[str]:
    return [raw.split("#", 1)[0].strip() for raw in gitignore_text.splitlines()]


def is_ignored(gitignore_text: str, entry: str = ENTRY) -> bool:
    """True when some line of ``gitignore_text`` already ignores ``entry``.

    Comments and trailing whitespace are stripped; a negation (``!.meta-harness``)
    is deliberately NOT treated as ignoring it, because it says the opposite.
    """
    present = set(_lines(gitignore_text))
    return bool(present & _EQUIVALENT.get(entry, frozenset({entry})))


def entry_to_append(gitignore_text: str | None) -> str | None:
    """The text to append to ``.gitignore``, or ``None`` when nothing is needed.

    ``None`` for ``gitignore_text`` means the file does not exist. A file that does
    exist and does not end in a newline gets one first, so the entry never joins
    itself to the project's last line.
    """
    missing = [
        artefact
        for artefact in ARTEFACTS
        if gitignore_text is None or not is_ignored(gitignore_text, artefact)
    ]
    if not missing:
        return None
    body = COMMENT + "\n" + "".join(f"{artefact}\n" for artefact in missing)
    if gitignore_text is None:
        return body
    prefix = "" if gitignore_text.endswith("\n") or not gitignore_text else "\n"
    blank = "\n" if gitignore_text.strip() else ""
    return f"{prefix}{blank}{body}"


def ensure_ignored(project_root: Path) -> str | None:
    """Ensure ``.meta-harness/`` is ignored. Returns a line to print, or ``None``.

    Returns ``None`` when nothing changed — already ignored, or the file could not
    be written. Never raises: adoption must not fail because of a read-only
    ``.gitignore``; the worst case is the status quo the project already had.
    """
    path = Path(project_root) / ".gitignore"
    try:
        existing: str | None = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = None
    except OSError:
        return None

    addition = entry_to_append(existing)
    if addition is None:
        return None

    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(addition)
    except OSError:
        return None
    verb = "created" if existing is None else "added the gate's output paths to"
    return f"{verb} {path}  (borromeanRings writes its receipts and coverage data there)"
