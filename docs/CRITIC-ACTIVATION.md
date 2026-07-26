# Activating the T2 critics

The Wave-2 semantic critics — **doc-drift** (`55_doc_drift`) and the **rubric
family** (`56_critics`: error-handling, naming, security, boundary-value,
test-smell) — ship **built but dormant**. They judge code against a rubric using a
model *external to the generator* (fail-closed), but do nothing until a judge is
wired. This is deliberate: a non-deterministic model call does not touch the gate
until you turn it on. See ADR-0023 / 0030 / 0036.

## The judge contract

A judge is any command that **reads a prompt on stdin and prints an answer
starting with `yes` or `no` on stdout**. The critics are fail-closed — only an
answer beginning with `y` passes; everything else (including errors) fails the
criterion. So a missing or broken judge can never silently pass a gate.

`scripts/critic-judge.sh` is a provider-agnostic judge that satisfies this
contract. First available provider wins:

1. the **`claude` CLI** on `PATH` (natural when borromeanRings runs inside Claude Code);
2. **`ANTHROPIC_API_KEY`** (+ `python3`) → the Anthropic Messages API (stdlib only);
3. neither → prints `no: …` (fail-closed).

## Turn it on

### 1. Advisory (recommended first) — reports, never blocks

```toml
# borromeanrings.toml
[critic]
judge_command = "bash scripts/critic-judge.sh"
rubrics = ["error_handling", "naming", "security", "boundary_value", "test_smell"]
```

Provide a provider:
- **Local (Claude Code):** nothing to do — the `claude` CLI is used automatically.
- **CI:** add `ANTHROPIC_API_KEY` as a repo secret and expose it to the gate step:

  ```yaml
  # .github/workflows/verify.yml — the gate step
  - name: Run borromeanRings gate (incl. CI-tier heavy checks)
    run: bash verify.sh --heavy
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      BORROMEANRINGS_JUDGE_MODEL: claude-sonnet-5   # optional
  ```

Now `55_doc_drift` / `56_critics` run and **report** drift/smells in the receipts —
still advisory (not in `[checks].required`), so they never block.

### 2. Gating (once you trust it) — blocks on failure

Move the critic checks to the **heavy lane** and require them, so a model call
only ever gates in CI (never on the fast Stop gate):

```toml
[checks]
heavy = ["60_mutation", "70_pip_audit", "72_licenses", "55_doc_drift", "56_critics"]
```

…and set `required=True` in the critic checks (flip the `evaluate*` call). Promote
one rubric at a time; watch the advisory signal first.

## Cost note

Each rubric judges each function with one model call. Keep it on the **heavy lane**
(CI), scope with `[critic].rubrics`, and consider a semantic cache (see the
agent-enhancement recommender: `python3 -c "from meta_harness.enhancements import
main; print(main())"`).
