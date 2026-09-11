# ADR-0080 — The gate's trusted Python must not run with the project on sys.path

**Status:** Accepted

## Context
`verify.sh` is THE GATE: CI checks out a PR branch and runs `bash verify.sh --heavy`
with the repo as `PROJECT_ROOT`, and the required `gate` check is whatever that exits.
The gate's own trusted Python — the verdict aggregation (`verify.sh`), language
detection (`verify.sh`), the receipt writer `emit_receipt` and the config read
`borromeanrings_project_cfg` (`checks/_lib.sh`) — ran as `python3 -` / `python3 -c`
**from the working directory CI runs it in, which is `PROJECT_ROOT`**. Python puts the
working directory first on `sys.path`, so a file named like a stdlib module — a
`json.py` committed at the project root — is imported in place of the real one.

#222 reproduced the full exploit against the CI command on `origin/dev`: a root-level
`json.py` that prints `  RESULT: PASS` and exits 0 when it detects the verdict step
makes `bash verify.sh` exit 0 on a genuinely failing tree. That forges the merge gate
— borromeanRings' whole premise is that the agent under test cannot forge the verdict,
and here it could. `07_layout` restricts only root `*.md` files, so nothing flagged the
planted `.py`; only a human reading the diff stood between it and a green `gate`.

This is the same shadowing class #221 (ADR for the substrate hooks) closed for the five
Stop/PreToolUse hooks with a `borromeanrings_py` helper that runs Python from `/`. The
gate did not share that helper.

## Decision
Add `checks/_py.sh` — a tiny sourced file defining `borromeanrings_py`, the only way
the gate starts a **trusted, verdict-deciding** Python:

```sh
borromeanrings_py() { (cd / && PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 "$@"); }
```

`/` is root-owned, so nothing can be planted there; `PYTHONPATH` still points at
borromeanRings' own `src`, which is how `meta_harness` resolves. `verify.sh` and
`checks/_lib.sh` both source it (checks get it transitively — every check already
sources `_lib.sh`). Every project path is already passed as an absolute argument, so
the `cd /` never loses one.

Routed: the four calls #222 names (verdict, language detect, `emit_receipt`,
`borromeanrings_project_cfg`) **plus** every borromeanRings-owned analysis heredoc whose
stdout/exit code becomes a required check's status: `05_hygiene`, `06_git_identity`,
`07_layout`, `08_branch`, `09_commits`, `11_changelog`, `12_secrets`, `13_adr`,
`14_container`, `15_a11y`, `32_complexity`, `33_coupling`, `34_api_diff`,
`35_architecture`, `45_docstrings`, `55_doc_drift`, `56_critics`, `74_secret_history`.
These are cwd-independent already (git runs via `git -C "$PROJECT_ROOT"` in the shell;
Python reads only absolute-path args), so routing them is safe and closes the residual
path where a plant shadows a single failing heredoc check into a genuine pass receipt.

Explicitly **not** the interpreter's `-P` / `-I` flags: `-P` exists only from 3.11 and
`requires-python` is 3.10 (#223), where it is an unknown option; CI runs 3.12 only, so
the break would be invisible — a version-specific flag CI cannot see would reintroduce
the very class. `-I` also discards `PYTHONPATH`. A neutral working directory is the
version-agnostic fix.

## Alternatives considered
- **`python3 -P` / `-I`** — rejected, above: 3.10-invisible / drops `PYTHONPATH`.
- **`cd "$BORROMEANRINGS_HOME"` instead of `/`** — rejected: when borromeanRings governs
  itself, `BORROMEANRINGS_HOME == PROJECT_ROOT`, so a `json.py` planted in its own root
  would still shadow. `/` is neutral under self-governance too.
- **Route every `python3` in every check, including the tool runs** — rejected. The
  tool runs (`00_build` compileall+import, `30_typecheck` mypy, `40_test` pytest,
  `60_mutation` mutmut, `70_pip_audit`, `72_licenses`) execute the **project's own
  code** by design; that code is already trusted regardless of cwd (a `conftest.py`
  forges pytest's result — #218), so routing them buys no security and would break test
  and tool discovery (pytest must run from `PROJECT_ROOT`). Closing *that* class is the
  M7 executor-isolation milestone, out of scope here — the same limit that keeps the
  Stop-hook half of #222 (forged `last_green_state`, hook markers) open.
- **Make `07_layout` flag stray root `.py`** — worthwhile but orthogonal; it narrows
  discoverability, it does not stop the shadowing. Deferred.

## Consequences
- (+) The gate's verdict can no longer be forged by a stdlib/`meta_harness` name planted
  in the governed project. `tests/integration/test_verify_no_sys_path_forge.py` plants a
  `json.py`, proves it wins the import race, and asserts a failing tree still reports
  FAIL — RED on pre-fix `dev`, GREEN after.
- (+) One helper now owns "how the gate starts trusted Python", mirroring the hooks'
  `borromeanrings_py`; new trusted calls have an obvious, safe front door.
- (−) The Stop-hook half of #222 (in-tree records the hook trusts without
  authentication) remains, blocked on M7. This PR closes only the `verify.sh`
  self-certification, which is independently fixable and is the higher-severity half
  (it forges the CI merge gate, not just the local loop).
