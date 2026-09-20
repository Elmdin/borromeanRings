# ADR-0088 — A check that cannot read its inputs fails, and shares one way of saying so

**Status:** Accepted · 2026-09-19 · issue #186 ·
**Relates to:** ADR-0049 (honest `noop`), ADR-0026 (receipts), ADR-0087 (git identity),
#256 (probes are not bounded)

## Context

ADR-0049 made the *verdict* fail-closed by allowlist. Inside individual checks, though,
"I could not read my inputs" still collapsed into "there was nothing to read":

```sh
changed="$(git -C "$PROJECT_ROOT" diff --name-only "$base"...HEAD 2>/dev/null || true)"
# ... the verdict is then computed from $changed
```

A crashed git, a corrupt index, a deleted object store — each yields an empty string,
which reads as "nothing changed", and the check reports a clean pass over a tree it never
read. The audit for #186 found this shape in twelve places; a re-audit on 2026-09-19
confirmed seven of the nine originally listed were still live, and found four more.

This is the project's own failure mode, in the checks rather than in the verdict: a green
that means "nothing was inspected". It cannot be fixed one script at a time, because the
fix keeps being re-typed slightly differently — #164 fixed it in `15_a11y`, and #179 hit
the same gap on a sibling branch because the fix lived in one script.

## Decision

1. **One helper, in `checks/_lib.sh`.** `borromeanrings_git_capture <out> <err> <args…>`
   asks git something about the governed project, bounded by the check's wall-clock
   limit, and returns **git's real exit status**. On success the answer is in `<out>` and
   `<err>` is empty; on failure `<out>` is empty and `<err>` carries git's own words. It
   never returns an empty answer with an empty error — the ambiguity that was the bug.
2. **One verdict for it.** `borromeanrings_cannot_read <id> <cmd> <log> <what> <error>`
   names what could not be read, quotes the tool, writes a `fail` receipt and exits. Not
   a `pass`, and deliberately not a `noop`: `noop` means "there was nothing to inspect",
   which is exactly what is *not* known here (ADR-0049).
3. **Exit statuses are read, not flattened.** `merge-base` exits 1 for "no common
   ancestor", which is an answer; anything above that is a failure. A caller says which
   it means rather than treating both as an empty string.
4. **A ratchet, not a promise.** `tests/integration/test_no_swallowed_git.py` scans every
   check for the old shape. Sites not yet converted are listed there *with the reason
   each is still there*, so the list shrinks deliberately and a new one cannot be added
   quietly. The list only ever gets shorter.

## Alternatives considered

- **Fix each site by hand, no helper.** How the last three attempts went (#164, #179, and
  the twelve sites this ADR inherits). The pattern is short enough to retype and subtle
  enough to retype wrongly, and each fix has to re-derive "what does an empty answer
  mean here".
- **A lint rule only** (`16_shellcheck` or a new check), with no helper. Flags the shape
  but offers nothing to replace it with, so every site invents its own handling and the
  rule becomes something to work around. The scan is worth having *beside* the helper,
  which is what point 4 is.
- **Make every check `set -e`.** Would turn a failed command into an aborted check —
  but an aborted check writes no receipt, and "no receipt" is a *worse* signal than a
  fail: the gate has to infer what happened. The receipt is the product; a check must
  live long enough to write one.
- **Treat an unreadable input as `noop`.** Rejected: `noop` is counted and reported as
  "inspected nothing, legitimately". Putting failures in that bucket would corrupt the
  one number this project uses to detect hollow greens.

## Consequences

- (+) Seven sites converted in one change, each with a test that fails on the old code:
  `09_commits`, `11_changelog`, `13_adr` (twice), `06_git_identity`, `17_prior_art`,
  `34_api_diff`, `76_lockfile`.
- (+) The next check that asks git something has a helper to use and a test that notices
  if it does not.
- (−) Four sites remain on the old shape, listed in the scan with their reasons: two
  `rev-parse --show-prefix` probes where a failure means "no repository", `08_branch`'s
  upstream probe (where "no upstream" is the documented answer), and
  `06_git_identity`'s repository probe (ADR-0087 records why git cannot distinguish the
  cases there).
- (−) The Python-side sites (`74_secret_history`, `34_api_diff`'s `git show`) need the
  same idea in Python — `subprocess.run(...)` without `check=`, whose `.stdout` decides
  the verdict. They are still open under #186 and are not covered by the shell scan.
- (−) `printf -v` is how the helper returns a value, and shellcheck cannot see that as an
  assignment; converted sites declare the variable first, with a comment saying why.
