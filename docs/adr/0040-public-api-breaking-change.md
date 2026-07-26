# ADR-0040 — Public-API breaking-change detection

**Status:** Accepted (justified by ADR-0039)

## Context
A library's public API is a contract; removing a symbol, renaming a parameter, or
adding a required argument silently breaks consumers (matrix row **D**). This was
deferred as *unjustified for the meta-harness* (no external API consumers). The
`examples/textkit` library (ADR-0039) is the real need that justifies it.

## Decision
Add `34_api_diff` + `meta_harness.api_diff`: diff the public signature surface of
`src` against the merge-base and fail on backwards-incompatible changes unless
`[api].allow_breaking=true`. Native stdlib `ast` + git; enabled on `textkit`,
not on borromeanRings itself.

## Alternatives considered
- **A tool (`griffe`, `pyanalyze`, ABI checkers)** — rejected as the mechanism:
  the import graph / AST is already native here, and signature-shape diffing is a
  small covered module. A tool is worth it only for deep type/overload analysis.
- **Compare against a published baseline / previous tag** — cleaner semver story,
  but rejected for now: the merge-base diff catches breaks *at PR time* (before
  they land) with no release-tagging ceremony; tag-based diffing can layer on when
  the project actually tags releases.
- **Always fail on breaks (no escape)** — rejected: intended breaking releases
  exist. `[api].allow_breaking` makes a break a *deliberate, declared* act (the
  semver major bump), not an accident — which is exactly the discipline wanted.
- **Enable it on borromeanRings too** — rejected per its own "no premature
  building" rule: the meta-harness's modules aren't an external API contract, so
  the check would fire on internal refactors with no real consumer to protect.

## Consequences
- (+) A library governed by borromeanRings can't silently break its API; the gate
  names the exact break and forces an explicit `allow_breaking` decision.
- (+) Proves the "justified building" thesis: the check exists because a real
  project (textkit) needs it — dogfooded and adversarially verified.
- (+) Native, 100% covered, portable across git-root and subdir projects.
- (−) Signature-shape only — it won't catch behavioral/type breaks (a param whose
  accepted type narrows). A type-aware pass is a future extension.
