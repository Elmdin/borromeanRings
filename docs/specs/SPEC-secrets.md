# SPEC — Secret scanning (high-confidence)

**Status:** Implemented · **Realized by:** `src/meta_harness/secrets.py`,
`checks/shared/12_secrets.sh` · ADR-0032

## Problem

Nothing stopped a hard-coded credential from landing in the tree (matrix row
**C — secret scanning**). A committed secret is compromised the moment it is
pushed.

## Contract

`12_secrets` scans **tracked** files for **high-confidence** secret shapes and
fails closed on any match:

| Kind | Shape |
|---|---|
| private-key-block | `-----BEGIN … PRIVATE KEY-----` |
| aws-access-key-id | `AKIA` + 16 upper/digits |
| github-pat / fine-grained | `ghp_…` / `github_pat_…` |
| slack-token / slack-webhook | `xox[baprs]-…` / `hooks.slack.com/services/…` |
| google-api-key | `AIza…` |
| stripe-secret-key | `sk_live_…` / `rk_live_…` |

- **Deliberately low false-positive:** only well-formed provider tokens and
  private keys — shapes that almost never occur by accident. The noisy part
  (generic entropy / secret-named assignments) is left to a tool (**gitleaks**)
  on the CI heavy lane; a T0 gate that cries wolf gets disabled.
- **Escape hatch:** a line carrying `borromeanrings: allow-secret` is skipped
  (documented examples/fixtures).
- Receipts report kind + location + a **truncated** snippet (never the full
  secret).

## Design

Pure `scan_text` / `scan_files` (text/paths in, findings out), 100% covered;
binary/unreadable files are skipped. The check feeds the NUL-delimited
`git ls-files` list via a file (not stdin — the heredoc owns stdin; an earlier
draft that piped it scanned nothing, caught by an adversarial probe). Native
stdlib `re`; no external tool.
