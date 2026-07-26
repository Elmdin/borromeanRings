# ADR-0032 — Native high-confidence secret scanning

**Status:** Accepted

## Context
No check stopped a hard-coded credential from being committed (matrix row **C**).
A secret is burned the instant it is pushed to a public repo, so this is a
security-tier gap. The gate keeps its external-tool footprint small and must run
fast on every Stop.

## Decision
Add `12_secrets` + `meta_harness.secrets`: scan tracked files for a curated set of
**high-confidence** secret shapes (provider tokens, private-key blocks) natively
via stdlib `re`, fail closed on any match. A `borromeanrings: allow-secret` line
marker whitelists documented examples. Snippets in receipts are truncated.

## Alternatives considered
- **gitleaks / trufflehog / detect-secrets (the real tools)** — better recall
  (entropy analysis, many rules), but rejected as the *T0* mechanism: a required
  external tool enlarges every governed project's footprint and can't run in the
  fast local gate without install. They belong on the **CI heavy lane** for the
  noisy/entropy detection; this native scan covers the high-value, unambiguous
  cases everywhere, cheaply. (Recorded as the heavy-lane follow-up.)
- **Generic "secret-named var = long string" / Shannon-entropy heuristics** —
  rejected for the T0 gate: they are where false positives live, and a gate that
  cries wolf gets ignored or disabled. High-confidence provider shapes have a
  near-zero false-positive rate (verified: 0 findings on borromeanRings's own
  tree), which is what makes a blocking check tolerable.
- **Scan the whole working tree (not just tracked files)** — rejected: it would
  flag build artifacts, `.meta-harness/receipts`, virtualenvs. Tracked files are
  exactly what a commit would publish.

## Consequences
- (+) An obvious credential can no longer be committed; the receipt names the
  file/line with a truncated snippet (never the full secret).
- (+) Zero dependency; `secrets.py` pure and 100% covered; the scan is reusable
  for any governed repo.
- (+) An adversarial probe (plant AKIA key → must fail) is part of validation —
  and it caught a real bug (a heredoc/stdin clash made the first draft scan
  nothing). Verifying detection, not just non-detection, is the point.
- (−) High-confidence-only means **lower recall** than gitleaks — a bespoke or
  generic secret can slip past. Accepted: the heavy-lane tool closes that gap;
  this is the cheap, always-on floor.
