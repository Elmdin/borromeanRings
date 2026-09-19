#!/usr/bin/env bash
# 26_citations — does what the changed docs cite actually exist on this branch?
#
# The largest defect class this repo's review cycle found is doc overclaim, and its
# mechanical half is a dead in-repo reference: a doc citing `docs/HANDOFF.md` on a base
# where that file lives only on another branch; `ADR-0057` cited bare where docs/adr/
# stops at 0047; `docs/CHECKS.md` described as being "on this base" when it is not. Those
# are path-resolution facts, not judgements — the 13_adr pattern applied to prose.
#
# Honest limits, because a gate that implies more than it verifies is the same defect:
# external URLs are NEVER checked (that needs a network; this runs on every gate) and
# issue/PR numbers are NEVER checked (that truth lives in GitHub's mutable state). Whether
# prose *describes* the code correctly stays with review and 55_doc_drift (ADR-0030).
# Off unless [citations].enabled. See docs/specs/SPEC-citations.md, ADR-0073.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"

id="26_citations"
log="$RECEIPT_DIR/$id.log"
cmd="citation resolution (changed docs cite only what this branch contains)"

fail_closed() {
  printf '%s\n' "$1" >>"$log"
  emit_receipt "$id" "$cmd" 1 "$log" "fail"
  exit 1
}

: >"$log"

# Fail closed if the config cannot be read. A `noop` here would report green for a check
# that never ran — the exact indistinguishability ADR-0049 exists to remove.
if ! enabled="$(borromeanrings_project_cfg citations_enabled 2>>"$log")"; then
  fail_closed "cannot read [citations] from borromeanrings.toml — failing closed"
fi
if [ "$enabled" != "True" ]; then
  echo "[citations].enabled is not set — no citation rule declared for this project" >>"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

if ! git -C "$PROJECT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "not a git repository — no branch to resolve citations against" >>"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

base=""
for candidate in origin/dev dev origin/main main; do
  if git -C "$PROJECT_ROOT" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
    base="$candidate"
    break
  fi
done
if [ -z "$base" ]; then
  echo "no base branch to diff against — nothing to check" >>"$log"
  emit_noop "$id" "$cmd" "$log"
  exit 0
fi

# Past this point git IS available inside a real repository, so a git failure is an
# undecidable state, never an empty one: fail closed rather than answer from worse
# evidence (the 12_secrets doctrine, ADR-0042).
if ! merge_base="$(git -C "$PROJECT_ROOT" merge-base HEAD "$base" 2>>"$log")" ||
  [ -z "$merge_base" ]; then
  fail_closed "cannot compute the merge base against '$base' inside a repository — failing closed"
fi

# --relative keeps paths correct for a git-root OR subdirectory project. --diff-filter=d
# drops deletions: a citation in a file this branch REMOVES is a claim being withdrawn.
if ! changed="$(git -C "$PROJECT_ROOT" diff --relative --name-only --diff-filter=d \
  "$merge_base"...HEAD 2>>"$log")"; then
  fail_closed "git diff failed inside a repository — failing closed"
fi
# Resolution is against TRACKED paths, never the bare filesystem: an untracked scratch
# file is not "on this branch" and must not be able to satisfy a citation.
if ! tracked="$(git -C "$PROJECT_ROOT" ls-files 2>>"$log")"; then
  fail_closed "git ls-files failed inside a repository — failing closed"
fi

PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 - \
  "$PROJECT_ROOT" "$PROJECT_ROOT/borromeanrings.toml" "$changed" "$tracked" >>"$log" 2>&1 <<'PY'
import re
import sys
from pathlib import Path, PurePosixPath

from meta_harness.citations import Citation, citations, heading_slugs, render, unresolved
from meta_harness.spine import load_config

root = Path(sys.argv[1])
cfg = load_config(sys.argv[2])
changed = [line for line in sys.argv[3].splitlines() if line.strip()]
tracked = frozenset(line for line in sys.argv[4].splitlines() if line.strip())
adr_dir = cfg.adr_dir.rstrip("/") + "/"


def _under_scanned_paths(path: str) -> bool:
    """Is this changed file one the project asked to have checked?"""
    return any(
        path == prefix or path.startswith(prefix.rstrip("/") + "/")
        for prefix in cfg.citations_paths
    )


docs = [path for path in changed if path.endswith(".md") and _under_scanned_paths(path)]
if not docs:
    print("no changed Markdown under [citations].paths — nothing to check")
    sys.exit(3)


def _tracked_path(target: str) -> bool:
    """A tracked file, or a directory some tracked file lives under."""
    return target in tracked or any(path.startswith(target + "/") for path in tracked)


def _tracked_anchor(target: str) -> bool:
    """The file is tracked AND the fragment names one of its headings."""
    path, _, fragment = target.partition("#")
    if path not in tracked:
        return False
    try:
        body = (root / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return fragment.lower() in heading_slugs(body)


def _tracked_adr(target: str) -> bool:
    """Some record under [adr].dir carries this four-digit number."""
    number = target.split("-", 1)[1]
    return any(
        path.startswith(adr_dir) and PurePosixPath(path).name.startswith(number)
        for path in tracked
    )


def _tracked_check(target: str) -> bool:
    """Some checks/<language>/<id>.sh exists on this branch."""
    pattern = re.compile(rf"checks/[^/]+/{re.escape(target)}\.sh")
    return any(pattern.fullmatch(path) for path in tracked)


RESOLVERS = {
    "path": _tracked_path,
    "anchor": _tracked_anchor,
    "adr": _tracked_adr,
    "check": _tracked_check,
}


def resolve(citation: Citation) -> bool:
    """The injected resolver: does this citation resolve on this branch?"""
    return RESOLVERS[citation.kind](citation.target)


findings: list[tuple[str, Citation]] = []
for doc in docs:
    try:
        text = (root / doc).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        # "I could not read it" is not "it was clean" (ADR-0049).
        print(f"cannot read changed document {doc}: {error}")
        print("failing closed — an unreadable document is not a checked one")
        sys.exit(1)
    parent = str(PurePosixPath(doc).parent)
    base = "" if parent == "." else parent
    found = citations(text, base=base, adr_dir=cfg.adr_dir)
    findings += [(doc, item) for item in unresolved(found, resolve)]

if findings:
    print(render(findings))
    sys.exit(1)
print(f"{len(docs)} changed document(s): every citation resolves on this branch")
PY
code=$?
status="$(borromeanrings_status_for_code "$code")"
[ "$status" = "noop" ] && code=0
emit_receipt "$id" "$cmd" "$code" "$log" "$status"
exit "$code"
