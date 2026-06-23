# ADR-0016 — Skip the Stop gate when the governed state is unchanged

**Status:** Accepted

## Context
The Stop hook (`stop_gate.sh`) ran the full gate (`verify.sh`: build → format → lint →
typecheck → test+coverage → security) on **every** agent turn, unconditionally. When the
agent only answered a question or edited a non-governed file (e.g. wrote a `.txt`), the entire
suite still ran — minutes of wall time and a large share of token/compute budget for **zero**
added assurance, since nothing the gate verifies had changed. This was the Maintainer's reported
inefficiency ("it still runs Stop hooks even though nothing was changed").

A second, related defect: `40_test.sh` ran `pytest --cov` without erasing stale coverage data,
so an orphan parallel file (`.coverage.<host>.<pid>`) from a crashed run poisoned coverage's
combine step (`no such table: other_db.file`) and **failed the gate for a non-code reason**.

## Decision
**No-op Stop guard (content-hash cache).** On a successful gate, `verify.sh` records a SHA-256
over the *gated inputs* — the governed source (`src_dir`), tests (`tests_dir`), the check scripts
(`checks/`, when borromeo governs itself), and `borromeo.toml` + `pyproject.toml` — to
`.meta-harness/last_green_state`. Before running the gate, the Stop hook recomputes that hash and
**skips** (exit 0) iff it byte-for-byte matches the last proven-green state. Logic lives in
`meta_harness/change_detect.py` (unit-tested to 100%).

This does **not** violate the "never pass on trust" red line (VISION §6). The gate verdict is a
deterministic function of the gated inputs; an identical input set has an identical verdict, so we
already hold proof for this exact state. It is caching a proof, not trusting an unverified change.

**Fail-closed everywhere:** no recorded state, any change to a gated input, or any read/compute
error ⇒ do **not** skip (run the gate). Artifacts that never affect the verdict (`__pycache__`,
`.pyc`, `.git`, `.meta-harness`, tool caches) are excluded from the hash. A non-governed file
(a stray `.txt`) is outside the gated set, so it cannot force a redundant run — which is correct,
because the gate would not verify it anyway.

**Coverage erase.** `40_test.sh` now removes `.coverage`/`.coverage.*` before pytest, so the gate
fails only on real regressions, never on leftover artifacts.

## Alternatives considered
- **`git status --porcelain` clean-tree check** — rejected: misses uncommitted-but-already-tested
  states and conflates ignored artifacts with real changes; a content hash is exact.
- **Skip based on Claude Code's tool-use history (did any Edit/Write fire?)** — rejected: harness-
  specific, and breaks borromeo's substrate-neutrality; the hash works for any author/harness.
- **Always run (status quo)** — rejected: the inefficiency this ADR removes.

## Consequences
- (+) Pure-question / non-code turns skip the gate in ~tens of ms instead of minutes — the
  token/compute waste the Maintainer flagged is eliminated, with no loss of assurance.
- (+) The gate stops failing on stale coverage artifacts (fail-flaky → fail-only-on-real-regression).
- (+) Substrate-neutral: the guard is a property of the gated content, not of any harness's event log.
- (−) The hash binds to the *project's* gated files. When borromeo is *referenced* from another
  project, a change to borromeo's own check scripts in `BORROMEO_HOME` is not reflected in that
  project's `last_green_state`; such cross-repo invalidation is a follow-up (today: re-run `verify.sh`
  after upgrading borromeo, or delete `.meta-harness/last_green_state`).
