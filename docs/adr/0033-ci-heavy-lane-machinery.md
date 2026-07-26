# ADR-0033 — CI-tier "heavy" check lane (machinery)

**Status:** Accepted

## Context
The fast inner Stop gate fires on every agent turn, so it must stay quick. But the
most valuable remaining checks are *expensive*: mutation testing runs the whole
suite once per mutant; CVE audit and license scans hit the network; thorough
secret/dead-code tools are slow. Running any of these on the inner gate would make
the interactive loop unusable — yet they belong in CI. borromeanRings needs a
second lane: checks that run and gate **only in CI**, never on the Stop gate.

(The concept was introduced with the mutation ratchet, ADR-0022, but that PR
carried both the machinery and the mutation check; this ADR lands the **machinery
on its own** so tool-checks can be added incrementally.)

## Decision
Add a **heavy lane** to `verify.sh`:
- `--heavy` (or `BORROMEANRINGS_HEAVY=1`) additionally scans `checks/ci/` and, in
  the verdict, requires `[checks].heavy` on top of `[checks].required`.
- Without `--heavy`, `checks/ci/` is never scanned and `[checks].heavy` never
  gates — the inner Stop gate is unchanged.
- `Config.heavy_checks` parses `[checks].heavy`; `checks/ci/` is the home for
  heavy check scripts; the CI workflow runs `verify.sh --heavy`.

Landed **dormant**: `[checks].heavy = []` and no `checks/ci/` checks yet, so both
modes produce an identical verdict today. Tool-checks populate it in follow-ups.

## Alternatives considered
- **Put heavy checks in the normal set, gated by an env flag inside each check** —
  rejected: every check would re-implement the "am I in CI?" branch, and a missing
  guard would silently run a 10-minute mutation pass on someone's Stop hook. One
  lane, decided in one place (verify.sh), is the Single Choice.
- **A separate `verify-heavy.sh`** — rejected: duplicates the run/verdict logic and
  drifts from the real gate. One script with a flag keeps the verdict identical.
- **Always run heavy checks but mark them advisory** — rejected: advisory checks
  don't gate, so CVEs/mutation regressions wouldn't block a merge. The lane makes
  them *required in CI*, which is the point.

## Consequences
- (+) A home exists for expensive, high-value checks (mutation, pip-audit,
  gitleaks, licenses, property-based) that gate in CI without slowing the Stop gate.
- (+) Dormant and behavior-preserving today (both modes identical), so it's a safe,
  reviewable infrastructure step; tool-checks land independently on top.
- (+) `[checks].heavy` keeps the heavy set declared in the one policy spine,
  consistent with `[checks].required`.
- (−) Heavy checks can't be validated on the fast local gate — they're exercised in
  CI (or `verify.sh --heavy` locally once their tools are installed). An accepted
  cost of keeping the inner loop fast.
