#!/usr/bin/env bash
# borromeanRings — THE GATE.
#
# Governs the project at PROJECT_ROOT (the repo/folder you're working in) using
# borromeanRings's own code at BORROMEANRINGS_HOME (where this script lives). They are the same
# when borromeanRings governs itself; they differ when borromeanRings is *referenced* from
# another project — set BORROMEANRINGS_PROJECT (or CLAUDE_PROJECT_DIR), or run from that
# project's directory. Fail-closed: exits 0 only if every required check (declared
# in the project's borromeanrings.toml) produced a pass receipt. Identical verdict for any
# author (human / CI / agent hook).
set -uo pipefail

# Heavy (CI-tier) lane: `--heavy` (or BORROMEANRINGS_HEAVY=1) additionally runs +
# requires the checks/ci/ set — expensive checks (mutation, CVE audit, secret-scan
# tools) that must NOT run on the fast inner Stop gate. Off by default. See ADR-0033.

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${BORROMEANRINGS_PROJECT:-${CLAUDE_PROJECT_DIR:-$PWD}}"
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"
# The gate reads the repository at PROJECT_ROOT and nothing else. GIT_DIR, GIT_WORK_TREE
# and friends override `git -C`, so an inherited pair pointing at a clean decoy made every
# git-reading check (12_secrets first among them) inspect the decoy instead (#250 review).
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
  GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE \
  GIT_CONFIG GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS # config injected by environment, too
export BORROMEANRINGS_HOME PROJECT_ROOT

# borromeanrings_py: the gate's trusted Python must run from a neutral directory,
# never with the governed project on sys.path (a planted json.py / meta_harness/
# would otherwise shadow stdlib and forge the verdict — #222).
source "$BORROMEANRINGS_HOME/checks/_py.sh"
CONFIG="$PROJECT_ROOT/borromeanrings.toml"

# Which lanes this run is in. Fast (interactive): `--fast` runs the SAME required set, but
# tells each check it may narrow its scope to what the project declared for interactive
# work — today only 40_test, via [test].fast_paths. The Stop hook runs this lane so an
# agent is not held for the whole test suite on every turn; the full suite still gates
# pre-merge and in CI, and a project that declares no fast paths sees no change at all.
# meta_harness.lane owns the precedence (--heavy always wins) so it is unit-testable; a
# resolution failure refuses to run rather than guessing a lane. See ADR-0081.
_lane_line="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$@" <<'PY'
import os
import sys

from meta_harness.lane import resolve_lane

lane, heavy, scheduled = resolve_lane(sys.argv[1:], os.environ)
print(lane, "1" if heavy else "0", "1" if scheduled else "0")
PY
)" || _lane_line=""
read -r LANE HEAVY SCHEDULED <<<"$_lane_line"
if [ -z "${LANE:-}" ] || [ -z "${HEAVY:-}" ] || [ -z "${SCHEDULED:-}" ] || [ "$LANE" = "$HEAVY" ]; then
  echo "borromeanRings: could not resolve the run lane (fast/full/heavy/scheduled) — refusing to run." >&2
  exit 1
fi
export BORROMEANRINGS_LANE="$LANE"

# Which borromeanRings version is governing this run. `git describe` on borromeanRings's own
# repo reflects the exact code state (tag when clean, `-N-g<sha>-dirty` when ahead/modified,
# short SHA before the first tag); the VERSION file is the human-declared release fallback.
# Stamped into the gate output and the persisted Verdict so each governed project's evidence
# records what verified it — not just pass/fail. See ADR-0048.
HARNESS_VERSION="$(git -C "$BORROMEANRINGS_HOME" describe --tags --always --dirty 2>/dev/null || true)"
[ -n "$HARNESS_VERSION" ] || HARNESS_VERSION="$(cat "$BORROMEANRINGS_HOME/VERSION" 2>/dev/null || echo unknown)"
export HARNESS_VERSION

if [ ! -f "$CONFIG" ]; then
  if [ -f "$PROJECT_ROOT/borromeo.toml" ]; then
    # Pre-rename config name (issue #62): still honored (meta_harness.spine falls back to
    # it), but deprecated — say so on every run until the project renames the file.
    echo "borromeanRings: DEPRECATED config name borromeo.toml in $PROJECT_ROOT — still honored; rename it: git mv borromeo.toml borromeanrings.toml (see docs/RENAME.md)." >&2
  else
    echo "borromeanRings: no borromeanrings.toml in $PROJECT_ROOT — run borromeanRings's init.sh there first." >&2
    exit 1
  fi
fi

# borromeanRings adjusts to the project: run the language-agnostic 'shared' checks plus the
# An UNKNOWN ARCHETYPE or LANGUAGE is the exception, and refuses before any check runs
# (#79, ADR-0068). The distinction is deliberate: a malformed config is a fact each check
# can report on, but `archetypes = ["firmware"]` or `language = "rust"` is a claim about
# what this project IS. Everything derived from it would be wrong: vacuous archetype
# requirements, or — for a language — the Python lane run against a project that is not
# Python. Narrow on purpose: it refuses only for those two errors, so the
# fail-closed-per-check behaviour above is intact.
archetype_error="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$CONFIG" 2>&1 <<'PY' || true
import sys

from meta_harness.spine import ProjectClaimError, load_config

try:
    load_config(sys.argv[1])
except ProjectClaimError as exc:
    print(f"{exc.kind}\t{exc}")  # matched by TYPE, never by the message's wording
except Exception:
    pass  # any other config problem is the individual checks' to report
PY
)"
if [ -n "$archetype_error" ]; then
  case "$archetype_error" in
    language$'\t'*) echo "borromeanRings: cannot load $CONFIG — ${archetype_error#*$'\t'}" >&2 ;;
    *) echo "borromeanRings: refusing to run — ${archetype_error#*$'\t'}" >&2 ;;
  esac
  exit 1
fi
# per-language set selected by [project].language (default python).
# An invalid config is NOT refused here. Every check fails closed on its own and writes
# a receipt saying why, which is better evidence than one message and no receipts — see
# tests/integration/*::*_fails_closed_not_noop, which assert exactly that.
language="$(PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py -c \
  "from meta_harness.spine import load_config; print(load_config('$CONFIG').language)" 2>/dev/null)" ||
  language=""
if [ -z "$language" ]; then
  # The fallback is deliberate (each check still reports its own failure), but which LANE
  # runs is decided here: silently choosing python means a Go or TypeScript project is
  # checked by tools that find no source and report "nothing to inspect". Say it, so the
  # reader knows why nothing from their own language ran (audit of 2026-09-20).
  language="python"
  echo "borromeanRings: could not read [project].language from $CONFIG — running the" >&2
  echo "  '$language' lane; each check still reports its own failure below." >&2
fi

case "$language" in
  "" | *[!a-z0-9_-]*)
    echo "borromeanRings: invalid [project].language: '$language' (use [a-z0-9_-])." >&2
    exit 1
    ;;
esac

# Per-run, append-only evidence — stored with the GOVERNED project, not borromeanRings.
run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
RECEIPT_DIR="$PROJECT_ROOT/.meta-harness/receipts/$run_id"
export RECEIPT_DIR
mkdir -p "$RECEIPT_DIR"

# Run shared (language-agnostic) checks + the selected language's checks. Each writes
# its own receipt; the verdict is computed from receipts, never a check's exit alone.
scan_dirs=("$BORROMEANRINGS_HOME/checks/shared" "$BORROMEANRINGS_HOME/checks/$language")
# CI-tier heavy checks run ONLY under --heavy (never on the fast inner Stop gate).
[ "$HEAVY" = "1" ] && scan_dirs+=("$BORROMEANRINGS_HOME/checks/ci")
# The scheduled tier costs more than a pull request should pay: 14 of a 25-minute round
# for mutation testing alone. It runs against the trunk on a schedule (ADR-0090), and a
# run that skipped it says so in its verdict rather than looking like one that did not.
[ "$SCHEDULED" = "1" ] && scan_dirs+=("$BORROMEANRINGS_HOME/checks/scheduled")
for dir in "${scan_dirs[@]}"; do
  [ -d "$dir" ] || continue
  for check in "$dir"/[0-9]*.sh; do
    [ -e "$check" ] || continue
    bash "$check" || true
  done
done

# Fail-closed verdict + summary. Single source of the expected check set is the
# project's borromeanrings.toml (the policy spine). meta_harness is borromeanRings's own code.
PYTHONPATH="$BORROMEANRINGS_HOME/src" borromeanrings_py - "$CONFIG" "$RECEIPT_DIR" "$PROJECT_ROOT" "$HEAVY" "$HARNESS_VERSION" "$LANE" "$SCHEDULED" <<'PY'

import json
import os
import sys
from pathlib import Path

from meta_harness.archetypes import non_noop_violations
from meta_harness.change_detect import compute_state_hash, record_green
from meta_harness.evidence import LANE_FAST, LANE_HEAVY, evidence_from_receipt, read_intent
from meta_harness.generator import read_generator
from meta_harness.lane import (
    FAST,
    FAST_LANE_NOTE,
    FULL,
    SCHEDULED_TIER_NOTE,
    effective_lane,
)
from meta_harness.receipts import read_log_text, run_digest, verify_receipt
from meta_harness.spine import load_config
from meta_harness.timings import timings_line
from meta_harness.verdict import (
    RISK_RED,
    Verdict,
    advisory_failures,
    hollow_outside,
    append_history,
    is_failing,
    risk_band,
    status_label,
    write_last_verdict,
)

config_path, receipt_dir, project_root, heavy, harness_version, lane, scheduled = sys.argv[1:8]
# Every check has already run and written its own receipt by now — including the
# fail-closed ones a malformed config produces (ADR-0042). What must not happen is this
# step dying on the same config and leaving a Python traceback where the verdict goes:
# the run then has no verdict at all, which is the one output a gate owes its caller
# (audit of 2026-09-20).
try:
    config = load_config(config_path)
except Exception as exc:  # noqa: BLE001 — any unreadable config, reported as the verdict
    print(f"\n  borromeanRings gate  (project: {project_root})")
    print(f"  cannot read {config_path}: {exc}")
    print("  RESULT: FAIL (the config the gate is configured by could not be read)")
    print(f"  Each check's own receipt is in {receipt_dir}.")
    # Record the failure before leaving, or the project's last_verdict.json still holds
    # the PREVIOUS run and status.sh reports a green that did not happen (review of
    # #261). The record carries no checks because none were graded — which is itself the
    # honest statement of what this run established.
    _unreadable = Verdict(
        ok=False,
        run_id=os.path.basename(receipt_dir),
        harness_version=harness_version,
        risk=RISK_RED,
        lane=lane,
    )
    write_last_verdict(Path(project_root), _unreadable)
    # And the history, for the same reason: a run the ledger never records is a failed
    # run that hid itself (review of #261, footnote).
    append_history(Path(project_root), _unreadable)
    sys.exit(1)
# Under --heavy the CI-tier heavy checks are also required; otherwise only the
# fast required set gates (the heavy set never blocks the inner Stop gate).
# Report the lane that describes the verification that actually happened: `--fast` in a
# project that declared no fast paths ran everything, and must not be labelled partial.
# An invalid declaration is already a clean FAIL receipt from 40_test; it must not also
# cost the run its table, its last_verdict.json, and its history line.
try:
    lane = effective_lane(config, lane)
except ValueError as exc:
    print(f"\n  borromeanRings: {exc}")
    lane = FULL
expected = (
    config.required_checks
    + (config.heavy_checks if heavy == "1" else ())
    + (config.scheduled_checks if scheduled == "1" else ())
)

rows = []
ok = True
intact_hashes = []
# What each check SHOWED (command, exit, log, hash) — carried on the verdict so a
# reviewer can trust a green that comes with proof, not just a status. See ADR-0056.
evidence = []
# Optional per-check one-liners (a receipt's `summary` field, e.g. 60_mutation's
# "evaluated N, score S"), printed beside the status. Only intact receipts contribute.
summaries = {}
# How long each check took, off its own receipt (#253). Reported, never judged: there
# is no budget here and this never touches `ok`.
durations = []
for cid in expected:
    rpath = os.path.join(receipt_dir, f"{cid}.json")
    if not os.path.exists(rpath):
        rows.append((cid, "MISSING"))
        ok = False
        continue
    with open(rpath) as fh:
        receipt = json.load(fh)
    status = receipt.get("status", "?")
    # Tamper-evidence: a required receipt must match its own content hash (fields +
    # log). A fresh run always does; a mismatch means the evidence was edited after
    # the fact — fail closed, never trust a forged/corrupt pass. See ADR-0026.
    # The log is read at its recorded path, or — when that path is gone because the
    # bundle was produced elsewhere and copied here (run-in-worktree.sh) — beside its
    # receipt. Reader-side resolution only: the hash still covers the log's content
    # and the recorded path string, so an edited log still fails. See ADR-0076.
    log_text = read_log_text(receipt, receipt_dir)
    if not verify_receipt(receipt, log_text):
        ok = False
        rows.append((cid, f"{status.upper()} !TAMPERED"))
        continue
    intact_hashes.append(receipt.get("content_sha256", ""))
    # `check_lane`, not `lane`: `lane` is the RUN's lane (fast/full, ADR-0081) and is
    # read after this loop for the verdict line and the record.
    # A scheduled check only ever runs in a run that is at least heavy (`--scheduled`
    # implies `--heavy`), so recording it as fast-lane evidence would misdescribe the run
    # it came from (ADR-0056; review of #263).
    expensive = cid in config.heavy_checks or cid in config.scheduled_checks
    check_lane = LANE_HEAVY if expensive else LANE_FAST
    evidence.append(evidence_from_receipt(receipt, lane=check_lane))
    # Fail-closed by ALLOWLIST, never by negation: only statuses meta_harness.verdict
    # declares non-failing (pass, noop) survive, so an unknown/typo'd/forged status
    # still fails. See ADR-0049.
    if is_failing(status):
        ok = False
    rows.append((cid, status.upper()))
    summaries[cid] = receipt.get("summary")
    durations.append((cid, receipt.get("duration_ms")))

# Archetype clause (ADR-0062): a check the declared [project].archetypes require to be
# non-noop but whose receipt is `noop` — or which is not in the expected set at all — turns
# the run FAIL. The one place an archetype overrides a check's own non-failing `noop`
# (ADR-0049): "inspected nothing" is legitimate for a greenfield project, not for a
# declared web app. No archetypes declared ⇒ empty tuple ⇒ behaviour unchanged.
archetype_failures = non_noop_violations(
    config.archetypes, {cid: status.lower() for cid, status in rows}
)
if archetype_failures:
    ok = False

width = max(len(c) for c, _ in rows)
print()
print(f"  borromeanRings gate  (project: {project_root})")
print(f"  harness-version: {harness_version}")
print("  " + "-" * (width + 14))
for cid, status in rows:
    # status_label validates + bounds the summary (untrusted JSON a check wrote).
    print(f"  {cid.ljust(width)}   {status_label(status, summaries.get(cid))}")
print("  " + "-" * (width + 14))
# Where this run's time went. A bound raised against no measurement is headroom, not a
# fix: 40_test hit the 900s check bound on dev and nothing said which check spent it.
slow = timings_line(durations)
if slow:
    print(f"  {slow}")
# A declared archetype names features the project must actually have. A check that
# noops where the archetype demands a real result is a violation, not an absence:
# "this project claims to be a CLI" and "no CLI entry point was inspected" cannot
# both be true (#79). Computed BEFORE the verdict because it DECIDES the verdict —
# printed after it, the line was an annotation on a run that still exited 0.
archetype_failures = non_noop_violations(
    config.archetypes, {cid: status.lower() for cid, status in rows}
)
for msg in archetype_failures:
    print(f"  ARCHETYPE: {msg}")
if archetype_failures:
    ok = False

print(f"  RESULT: {'PASS' if ok else 'FAIL'}{' (FAST LANE)' if lane == FAST else ''}")
# A narrowed run must say so on its own verdict line, not only inside one check's row: a
# fast-lane PASS is not the PASS a full run would have produced, and must never be read as
# one. See ADR-0081.
if lane == FAST:
    print(f"  {FAST_LANE_NOTE}")
# Which tiers this verdict covers. A green that did not run a tier must not read as one
# that did — the same rule the fast lane follows (ADR-0081, ADR-0090).
tiers = ["required"] + (["heavy"] if heavy == "1" else []) + (["scheduled"] if scheduled == "1" else [])
print(f"  tiers verified: {' + '.join(tiers)}")
if scheduled != "1" and config.scheduled_checks:
    print(f"  {SCHEDULED_TIER_NOTE}")
# A green built partly on checks that inspected NOTHING is not the same green as one
# where every check did real work. Say so here, or the verdict over-claims (ADR-0049).
hollow = [cid for cid, status in rows if status == "NOOP"]
if hollow:
    print(f"  inspected NOTHING: {len(hollow)} of {len(rows)} required — {', '.join(hollow)}")
# Every registered check runs, but only the required set is graded — so this line used to
# be silent on the run an adopter sees FIRST, when nothing is required yet and most of
# what ran inspected nothing (audit of 2026-09-20). The run dir knew; the verdict did not.
elsewhere = hollow_outside(receipt_dir, expected)
if elsewhere:
    # Receipts that exist and are NOT graded. Subtracting len(rows) was wrong: a
    # required check that wrote no receipt is still a row, so the count undercounted and
    # could go negative (review of #261).
    graded = {cid for cid, _ in rows}
    ran = len([p for p in Path(receipt_dir).glob("*.json") if p.stem not in graded])
    # Lowercase on purpose: the line above shouts about the GRADED set, and several tests
    # read "inspected NOTHING" as "a required check did no work". This line is the same
    # fact about checks that ran without being graded, and must not be confused with it.
    print(
        f"  also inspected nothing (not required, did not decide the verdict):"
        f" {len(elsewhere)} of {ran} that ran — {', '.join(elsewhere)}"
    )
# A failing check outside the expected set is reported, never hidden, and never decides
# the verdict (#229; verdict.advisory_failures).
advisory = advisory_failures(receipt_dir, expected)
if advisory:
    print(f"  advisory — not required, did not decide the verdict: {', '.join(advisory)}")
digest = run_digest(intact_hashes) if intact_hashes else ""
if digest:
    print(f"  run-digest: {digest}")
# Categorical risk band from the recorded statuses alone (red > hollow > green): it
# allocates human review attention and never relaxes the gate itself (ADR-0056).
checks = tuple((cid, status.lower()) for cid, status in rows)
risk = risk_band(checks)
print(f"  risk-band: {risk.upper()} · evidence: {len(evidence)} receipt(s)")
if not ok:
    print("  One or more checks failed or produced no receipt; see logs in the run dir.")
print()

# Persist a compact last-known verdict for the portfolio status view, and append it to
# the effectiveness-ledger history (best-effort: a write failure must never turn a real
# PASS into a FAIL). See ADR-0046 (status) and ADR-0047 (ledger).
try:
    # Intent: which branch/commit was gated, over which gated-input digest (the same
    # fingerprint the no-op Stop skip trusts), read from git with a fixed argv — and WHO
    # produced the change, self-declared by the adapter that ran the gate
    # (claude-code:<session>, headless:<command>). The generator is provenance, never
    # evidence: read AFTER `ok` is decided, recorded, never consulted; unset ⇒ ""
    # (ADR-0071 §4, ADR-0078).
    # Evidence is best-effort by contract (ADR-0056): whatever the digest raises, the
    # verdict's exit code must not depend on it — so this catches everything, not
    # just OSError, and records an empty digest ("not recorded"), never a crash.
    try:
        input_digest = compute_state_hash(Path(project_root), config)
    except Exception:  # noqa: BLE001 - best-effort evidence, gate exit must not depend on it
        input_digest = ""
    _verdict = Verdict(
        ok=ok,
        checks=checks,
        run_id=os.path.basename(receipt_dir),
        digest=digest,
        harness_version=harness_version,
        risk=risk,
        intent=read_intent(
            Path(project_root),
            input_digest,
            generator=read_generator(os.environ.get("BORROMEANRINGS_GENERATOR")),
        ),
        evidence=tuple(evidence),
        lane=lane,
    )
    write_last_verdict(Path(project_root), _verdict)
    append_history(Path(project_root), _verdict)
    # Make each receipt bundle self-describing: which borromeanRings produced it.
    Path(receipt_dir, "harness_version.txt").write_text(harness_version + "\n", encoding="utf-8")
except OSError:
    pass

if ok:
    # Record this exact gated-input state as proven-green so a no-op Stop (a
    # question, a doc edit) can skip a redundant full gate. Best-effort: a
    # recording failure must never turn a real PASS into a FAIL.
    try:
        record_green(Path(project_root), config)
    except OSError:
        pass
sys.exit(0 if ok else 1)
PY
