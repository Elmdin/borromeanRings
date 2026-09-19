# Survey — a shared home for state the governed project must not be able to write

**Question.** The Stop hook's no-op skip rested on a record inside the governed tree
(#222). Where should that record live, and did something already answer that question?

## What already exists

| Where | What was found | Fit |
|---|---|---|
| This repo | `meta_harness.retry_state` — `state_root`, `project_digest`, `counter_path`, `is_inside`, `_open_nofollow`, plus the legacy-migration walk. ADR-0079 already decided this exact question for the retry count: XDG state root, project named by the sha256 of its resolved absolute path, fail closed when no absolute root exists. | **Extend.** The question was already answered; what was missing was a way for a second consumer to reach the answer. |
| This repo | `meta_harness.receipts` — writes under `<project>/.meta-harness/receipts/`. | Not a fit: receipts are *evidence about* a run and belong with the project. This record *decides whether the run happens*, which is exactly what must not be project-writable. |
| This repo | `meta_harness.hook_dedupe` — claim markers under `.meta-harness/hook_markers/`. | Not a fit as a home, but it turned out to share the defect: a future-dated marker was believed. Fixed alongside. |
| A declared dependency | None. borromeanRings has no runtime dependencies — shell plus the standard library — and `platformdirs` (the obvious candidate) is not declared and would be the project's first. | Not a fit: `os.path.isabs` plus two env lookups is the whole requirement, and ADR-0079 already rejected *guessing* a location, which is the only thing a library would add. |
| Ecosystem | The XDG Base Directory Specification itself (`$XDG_STATE_HOME`, default `$HOME/.local/state`). Advisory — no key-free search exists, see ADR-0051. | **Reuse the specification**, including its rule that a relative `XDG_STATE_HOME` is ignored. |

## Decision

**Extend**, by extracting rather than re-deriving: `meta_harness.state_home` now owns
`state_root`, `project_digest`, `project_state_dir`, `StateUnavailable`, `DIGEST_CHARS`,
`DIR_FLAGS`, `is_inside` and `open_nofollow`, and `retry_state` imports and re-exports
them. Nothing new was invented; one module's private answer became the shared one, which
keeps the module graph acyclic (`35_architecture`) and means the retry count and the
last-green record cannot drift apart.

The *because* is the part worth recording: the first draft of #222 re-derived the location
logic in `change_detect` and left the protections behind. The review found two real bugs in
that gap — a symlinked `.meta-harness` steering a delete outside the tree, and a missing
containment guard that put the "outside the tree" record back inside it. Both were already
solved in `retry_state`. Copying an answer without copying its caveats is how this survey
would have been worth writing before the code rather than beside it.

`DIGEST_CHARS` is the concrete reason this had to be one module and not two agreeing ones:
if the two copies ever drifted, every existing retry counter would silently reset, and the
bound would quietly stop holding with nothing failing.

## Sources
- `docs/adr/0079-retry-count-outside-the-tree.md` — the decision this extends
- `docs/adr/0082-no-op-skip-state-outside-the-tree.md` — the decision this records
- XDG Base Directory Specification, `$XDG_STATE_HOME`
- `git grep -n "XDG_STATE_HOME\|state_root\|project_digest" src/` — how the existing answer was found
- The review on PR #232, which is where the "did you reuse the protections too?" question was actually forced
