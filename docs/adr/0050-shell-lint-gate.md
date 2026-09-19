# ADR-0050 — Shell lint gate (shellcheck)

**Status:** Accepted
**Spec:** `docs/specs/SPEC-shellcheck.md`
**Closes:** #52

## Context

borromeanRings gates Python with twenty checks. Its **shell** — 43 tracked scripts, ~2,800
lines — had none, and that shell is not incidental: it is the gate itself (`verify.sh`),
every check under `checks/`, the four Claude hooks that enforce governance in a session,
and `merge.sh`. **The trust root was the one part of the codebase nobody linted.**

That is the same shape of hole ADR-0049 closed: a gate that looks rigorous while being
blind to half the code it governs.

Running shellcheck over the suite found **five** issues, and two were real defects rather
than style:

- `scripts/critic-judge.sh` piped the prompt into `python3 - <<'PY'`. A heredoc supplying
  the program **overrides** a pipe on the same stdin, so `sys.stdin.read()` returned `""`
  — the API-key judge path had been sending an **empty prompt** to the model (SC2259).
- `.claude/hooks/pre_bash_guard.sh` had a dead `case` alternative in the
  **dangerous-command guard**: a pattern that could never match because an earlier one
  already subsumed it (SC2221/SC2222). Harmless in effect, but dead code in a security
  guard is exactly where it should not be.

Neither is reachable by any Python test. Only a shell linter would ever have found them.

## Decision

Add `16_shellcheck` (shared lane, required): shellcheck over the project's shell,
**fail-closed on any finding at any severity**. No threshold and no ratchet — a lint
finding is binary, the suite is small, and it starts at zero.

**Resolve sources, do not suppress them.** Scripts here `source` a sibling library through
a runtime-computed path (`$(dirname "${BASH_SOURCE[0]}")/../_lib.sh`), which shellcheck
cannot follow statically and reports as SC1091 — **33 times**. The obvious move is
`-e SC1091`, which would also mute genuine unreadable-source bugs. Instead the check
passes `-x` with `[shell].source_paths` (`SCRIPTDIR` = the checked script's own
directory), which resolves **all 33** properly. `[shell].exclude` remains a per-code
escape hatch and is empty; prior art (ESLint's single `--no-warn-ignored` suppressing
several distinct reasons at once) is the warning against coarse suppression.

**File list.** Git-tracked `*.sh` when the project is a repo, so an untracked scratch
script never fails someone's gate; a bounded filesystem walk otherwise, reusing
`source_coherence.walk_sources`. No tracked shell ⇒ `noop`, not a hollow `pass`
(ADR-0049) — a pure-Python project legitimately has none.

**No `xargs`.** On a long file list `xargs` splits into several invocations and returns
only the **last** exit code, silently dropping findings from earlier batches. One
invocation, one exit code.

**Tooling.** `shellcheck-py` is added to the dev extras: it ships the real binary as a
wheel, so CI needs no `apt` step and a local install matches CI exactly. A missing
shellcheck is `error`/127, never a skip — the ADR-0049 rule.

## Consequences

- The trust root is now linted to the same standard as the Python beside it, and two live
  defects are fixed as a direct result.
- Adopting the check on an existing project will likely go red first; that redness is the
  information the project was not getting. `[shell].exclude` exists for a genuinely
  inapplicable rule, with a written justification.
- One more required tool. It is pip-installable and pinned in the dev extras, so this
  costs no new system dependency.
- Shell-integration tests are excluded from mutmut's clean-test run (they resolve
  repo-relative paths that do not exist in the copied `mutants/` tree).
