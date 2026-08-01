# SPEC — Wave-2 critic rubric family

**Status:** Implemented (advisory) · **Realized by:**
`src/meta_harness/critic_rubrics.py`, `checks/python/56_critics.sh`,
`[critic].rubrics` · ADR-0036

## Contract

`56_critics` (advisory, opt-in) judges functions against declared rubrics using a
model judge external to the generator — the same machinery as doc-drift.

| Rubric | Scope | Judges |
|---|---|---|
| `error_handling` | src | bare/swallowed exceptions, unsurfaced failures |
| `naming` | src | misleading/cryptic names |
| `security` | src | injection / unsafe eval-exec / shell / traversal |
| `boundary_value` | src | unhandled empty/zero/negative/None edges |
| `test_smell` | tests | vacuous tests (no assert, asserts constant, over-mocked) |

- **Advisory:** not in `[checks].required`; reports, never gates, until promoted.
- **Opt-in:** no-op unless `[critic].judge_command` **and** `[critic].rubrics` set.
- **Fail-closed** per judgment (only explicit "yes" passes; a judge error is a
  failed criterion).
- **DRY:** a rubric is a `RUBRICS` registry entry — question + scope, no new
  plumbing.

Pure `extract_functions` / `run_rubric` (100% covered, stub judges). Wiring a
`judge_command` (e.g. `claude -p`) activates every enabled rubric at once;
promotion to gating is a heavy-lane + `required=True` step.
