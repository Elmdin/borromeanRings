# ADR-0056 — Evidence, intent and a categorical risk band in the verdict

**Status:** Accepted
**Spec:** `docs/specs/SPEC-verdict-evidence.md`
**Amends:** ADR-0046 (verdict record), ADR-0047 (ledger columns), ADR-0049 (self-status)
**Issue:** #134

## Context

The persisted verdict says *that* the gate was satisfied and which checks passed. It does
not say **what was shown to happen**. A reviewer who wants to trust a green must open the
receipt bundle and read, per check, which command ran, how it exited, whether its log is
empty, and whether the receipt's tamper-evident hash still matches. ADR-0049 made
"inspected nothing" visible in the verdict; the rest of the proof still lived only in
files nobody reads behind a green.

`docs/research/VIDEO-REVIEW.md` (Kun Chen's pipeline: intent → review → evidence
artifacts → a PR that carries intent / evidence / risk) is the origin: a change should
arrive with what it intended, what shows it works, and how much human attention it needs.

Two standing constraints shape the answer. **Threshold-free:** the maintainer rejects
numeric targets outright, so any "risk" must be categorical, derived from facts, and never
a score. **Fail-closed unchanged:** nothing about how `ok` is computed may move.

## Decision

**1. The verdict records evidence, not just status.** `meta_harness.evidence` lifts each
intact required receipt into an `Evidence` record — `command`, `exit_code`, `log`,
`log_bytes` (measured on disk at verdict time), `content_sha256`, and `lane` (`heavy` iff
the check is in `[checks].heavy`, else `fast`). Nothing new is written to receipts; the
verdict cites what `_lib.sh` already produced. A missing or tampered receipt gets **no**
evidence entry — there is nothing trustworthy to cite — and its row bands red.

**2. The verdict records intent.** `Intent` = branch, head SHA (both from `git rev-parse`
with a fixed argv, no shell — the `status.py` pattern) and `input_digest`, which is
`change_detect.compute_state_hash` over the gated paths: the same fingerprint the no-op
Stop skip already trusts, so a verdict can be matched to the exact tree it judged. Outside
a repo the git fields are `""`; the gate's outcome is never affected.

**3. A categorical risk band, derived only from recorded statuses.** `verdict.risk_band`
returns `red` if any status is failing (by the ADR-0049 allowlist — so an unknown status
is red, not ignored), else `hollow` if any check inspected nothing **or there were no
checks at all**, else `green`. Red beats hollow: a failure is never softened by a hollow
sibling. There is no numeric input anywhere in the derivation. The band is computed
*after* `ok`, from the same rows, and only reported: **no band ever relaxes a gate.**

**4. Back-compatibility is a read-side guarantee.** Old records parse with `risk == ""`,
`intent == Intent()`, `evidence == ()`. A missing band is rendered as *not recorded
(verdict predates evidence capture)* — never re-derived into `green`, which would be the
record claiming something it never claimed (the ADR-0049 discipline applied to itself).
Parsing is fail-soft field by field: a malformed nested value degrades to its default; a
malformed evidence entry is skipped, its siblings kept. `bool` is explicitly not an
integer here — a JSON `true` exit code must not become exit 1 — and an absent exit code
is `-1`, never `0`.

**5. Surfaced where verdicts are read.** The gate prints one line
(`risk-band: HOLLOW · evidence: 19 receipt(s)`); self-status adds `Risk band:` and
`Intent:` lines; the ledger gains an `EVIDENCE` column (`evidenced/runs`) and a tally
term, so evidence presence per run is visible across the portfolio.

## Alternatives considered

- **A numeric risk score** (weighted checks, coverage deltas). Rejected: threshold-free is
  a standing rule, and a score invites gaming and means nothing.
- **Bands from touched areas via `CODEOWNERS` groupings** (the issue's wording). Deferred:
  this branch has no `CODEOWNERS` file, and a band keyed to path groups needs that file
  to be the single source of truth rather than a second list of "sensitive paths" in
  the harness. The record shape here (`risk` is a free string from a declared set) is
  designed so a touched-area band can be added as a further category without a schema
  change.
- **Copy the log text into the verdict.** Rejected: the verdict must stay compact and
  readable; the log path + size + receipt hash let a reader fetch and verify the artifact.

## Consequences

- A green now arrives with its proof attached: which command, which exit, which artifact,
  which hash, on which commit. `last_verdict.json` stays pretty-printed and readable.
- Every gate run now reads the head SHA and computes the gated-input digest
  unconditionally (previously the digest was computed only on a PASS, via
  `record_green`). Both are fast and fail-soft.
- `LedgerSummary` gains a trailing `evidenced` field (default `0`) and `render` a column;
  the ledger's exact-row test was updated accordingly.
- `Verdict.to_dict()` gains three keys, so any consumer asserting the exact dict shape
  (one test did) sees the new empty-default keys.

## Deferred (from #134, not built here)

- **Touched-area bands from `CODEOWNERS`** — see above; needs the file first.
- **`merge.sh` refusing when the band requires absent evidence.** `merge.sh` already
  refuses on any gate failure (red). Refusing on `hollow` would block merges for every
  genuinely greenfield project (whose checks are honestly `noop`), which is a policy
  change with real blast radius and is not made silently here. When archetypes declare
  which checks must be non-`noop` (#79/#138), that declaration is the right input for a
  hollow-aware merge rule.
