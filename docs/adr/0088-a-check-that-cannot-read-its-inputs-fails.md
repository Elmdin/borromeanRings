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

## Amendment, 2026-09-20 — the same rule for the tools that measure

The first pass covered the checks that ask **git** something. The three ratchets measure
the project with a **tool**, and had the same shape from both sides:

```sh
read -r current worst < <(… borromeanrings_py - … <<'PY' … PY)   # status discarded
baseline="$(cat "$baseline_file" 2>/dev/null || echo 100000)"     # unreadable ⇒ permissive
```

Process substitution is worse than `|| true`: `$?` after it belongs to `read`, so even
an author who checks the status is told the wrong thing. A crashed measurement left
`current` empty, `[ "" -gt 100000 ]` *errored* rather than being false, the comparison
never fired, and the ratchet passed over a measurement nobody got.

Two more shared pieces, same shape as the first two:

- `borromeanrings_integer_or_fail` / `borromeanrings_number_or_fail` — a ratchet
  compares a measurement to a baseline, and **how** it compares decides what counts as a
  number. `32_complexity` and `33_coupling` use bash's `[ x -gt y ]`, which is
  integer-only: given `3.5`, or twenty digits, it does not return false — it *errors*,
  and with no `set -e` the comparison silently does not fire. So each caller says which
  kind it can actually compare, rather than sharing a validator that accepts "a number".
  (The first version of this amendment shipped the looser validator to all three; found
  by the security review of #259.)
- `borromeanrings_baseline` — **absent** is a legitimate default (an unconfigured
  project never fails); anything that **exists and cannot be read**, or is not a number
  of the kind that check compares, is a failure. "Absent" is `! -e && ! -L`, because
  `-e` follows symlinks and a *dangling* symlink would otherwise answer "does not
  exist" while being a file that is there and unreadable — the same review found that
  one too. `19_context_budget` already did this; now it is the shared rule rather than
  one script's good behaviour.

Converted: `32_complexity`, `33_coupling`, `45_docstrings` (measurement, baseline, and
the docstring comparison, which is itself a tool call).

## Amendment, 2026-09-20 (2) — the same rule inside the embedded Python

Two checks read git from inside their heredocs, where the shell helpers cannot reach:

```python
out = subprocess.run(["git", "-C", root, *args], capture_output=True).stdout
```

`.stdout` is empty when git **failed** and when git **found nothing** — the same
ambiguity as `|| true`, one language down. `74_secret_history` printed "empty history —
nothing to scan" and exited 0 over a history it could not list; `34_api_diff` read every
failure as "new file — no prior API to break", so a repository nobody could read
reported no breaking changes having compared nothing.

`meta_harness.git_read` is the Python side of the same decision: `git_text` / `git_bytes`
raise `GitUnavailable` carrying git's own words instead of returning an empty answer, and
`git_show` asks whether a path existed at a revision (`ls-tree`) rather than inferring it
from a failure. Every call is bounded by `BORROMEANRINGS_CHECK_TIMEOUT`, which also
closes the Python half of #256 — including when that variable holds something that is
not a finite number: `nan` and `inf` parse as floats without raising, and `nan <= 0` is
False, so a naive guard passed them straight to `subprocess.run`, where they wait
forever. Anything not finite falls back to the default, never to "unbounded" (found by
the security review of #260).

The scan grew a second half for this, reading exactly the heredoc bodies the first half
skips. It flags a git subprocess whose status nobody reads in any of its spellings:
`.stdout` chained straight off the call, the two-line `done = subprocess.run(…)` /
`done.stdout` (the most natural way to reintroduce the bug, and invisible to the chained
pattern — same review), `getattr(done, "stdout")`, `os.popen` and
`Popen(…).communicate()`. It does not flag reading `.returncode` first, nor
`check_output`, which raises. Verified against `dev`'s own copies: it flags all three of
the calls this amendment converts.

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

- (+) Ten sites converted in one change, each with a test that fails on the old code:
  `09_commits`, `11_changelog`, `13_adr` (branch, base and diff), `06_git_identity`,
  `17_prior_art` (branch, base, diff), `34_api_diff`, `76_lockfile`, `08_branch`
  (branch) — plus the base-branch resolution every one of them shares.
- (+) Two more helpers where the reasoning was being re-derived per check:
  `borromeanrings_head_branch` (which branch is this?) and `borromeanrings_base_ref`
  (what do we diff against?), both fail-closed.
- (+) **Legitimate states stay legitimate, and are measured rather than assumed.** In a
  repository with *no commits yet* `git rev-parse --abbrev-ref HEAD` exits 128 — HEAD
  names a branch that does not exist — so a naive "any failure fails the check" would
  turn every freshly initialised project red. `symbolic-ref` still knows the name, and a
  test pins it. A detached HEAD exits 0 with the name "HEAD", as it always has.
- (+) The scan flags **any** git call in shell whose exit status nobody reads — not a
  denylist of suppression idioms. A plain `x="$(git …)"` with no `$?` check is the most
  ordinary way to regress, and the first two versions let it through. It also flags the
  forms that lose the status *entirely*, where even a careful author checking `$?` would
  be told the wrong thing: backticks, `mapfile`/`read` from a process substitution, and a
  pipe into either. It exempts the two forms that DO read the status (`if ! x="$(git …)"`
  and `x="$(git …)" || handler`), comments, and heredoc bodies — the Python inside them
  is the other half of #186 and needs its own helper. Every one of those rules is pinned
  by a test. (Per-line keying, the wrapped call, the unread status and the statusless
  captures were each found by the security review of this PR, over three passes.)
- (−) **Five** calls remain on the old shape, listed in the scan **line by line** with
  the reason each is there: `08_branch`'s upstream probe and its `rev-list --count`
  (where "cannot judge" is the documented answer), two `rev-parse --show-prefix` probes,
  and `06_git_identity`'s repository probe (ADR-0087 records why git cannot distinguish
  the cases there).
- (−) The Python-side sites (`74_secret_history`, `34_api_diff`'s `git show`) need the
  same idea in Python — `subprocess.run(...)` without `check=`, whose `.stdout` decides
  the verdict. They are still open under #186 and are not covered by the shell scan.
- (−) `printf -v` is how these helpers return a value, and shellcheck cannot see that as
  an assignment; converted sites declare the variable first, with a comment saying why.
