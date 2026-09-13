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
| aws-access-key-id | `AKIA` + 16 upper/digits — the **public** half of the pair |
| aws-secret-access-key | an identifier matching `aws…(secret\|private)…` assigned a 40-char base64 value, **quoted or not** — the half that **grants access** |
| github-pat / fine-grained | `ghp_…` / `github_pat_…` |
| slack-token / slack-webhook | `xox[baprs]-…` / `hooks.slack.com/services/…` |
| google-api-key | `AIza…` |
| stripe-secret-key | `sk_live_…` / `rk_live_…` |

**This table is the covered set, and it is exhaustive.** A pattern without a row
here fails `test_every_pattern_has_a_planted_example`; a row without a working
example fails `test_each_planted_secret_is_detected`. The AWS secret key gap
(#230) survived because coverage was an impression rather than a list — the check
reported *"no high-confidence secrets in tracked files"*, which reads as an
assurance, over a credential it had never been taught to see.

- **Deliberately low false-positive:** only well-formed provider tokens and
  private keys — shapes that almost never occur by accident. The noisy part
  (generic entropy / secret-named assignments) is left to a tool (**gitleaks**)
  on the CI heavy lane; a T0 gate that cries wolf gets disabled.
- **Name plus shape is not entropy.** `aws-secret-access-key` is matched by the
  *identifier* alongside the value, never by the value alone: a bare 40-character
  base64 string is also every sha256 and every short blob, and flagging it would
  be the heuristic this check rejects. `BLOB = "<40 chars>"` is not a finding;
  `AWS_SECRET_ACCESS_KEY = "<40 chars>"` is. The value's **quotes are optional**,
  because the commonest home for this credential — `~/.aws/credentials` — is INI
  and has none, as do `.env` files, Dockerfile `ENV` and `export`. A terminator
  (quote, whitespace or end of line) is required instead, so a longer base64 run
  never matches its first 40 characters.
- **Required by default.** `init.sh` puts `12_secrets` in a new project's
  required set. It is not a ratchet — there is no baseline to seed and no
  threshold to meet — so "start green" does not apply: it only ever fires when
  there really is a credential in the tree.
- **Escape hatch:** a line carrying `borromeanrings: allow-secret` is skipped
  (documented examples/fixtures). The marker is **line-scoped**, and `ruff format`
  can wrap a long statement and carry the comment off the literal's line, silently
  revoking it — keep a marked literal short, or hoist it into its own constant.
  Giving the marker a layout-independent scope is open work (#230).
- Receipts report kind + location + a **truncated** snippet (never the full
  secret).

## Design

Pure `scan_text` / `scan_files` (text/paths in, findings out), 100% covered;
binary/unreadable files are skipped. The check feeds the NUL-delimited
`git ls-files` list via a file (not stdin — the heredoc owns stdin; an earlier
draft that piped it scanned nothing, caught by an adversarial probe). Native
stdlib `re`; no external tool.
