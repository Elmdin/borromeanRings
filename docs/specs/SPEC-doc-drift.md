# SPEC — Doc-drift critic (first live application of the T2 seam)

**Status:** Implemented (advisory) · **Realized by:**
`src/meta_harness/doc_drift.py`, `checks/python/55_doc_drift.sh`,
`[critic].judge_command` · ADR-0030 (extends ADR-0023)

## Problem

`45_docstrings` enforces that public definitions *have* a docstring, but nothing
checks the docstring still tells the truth. "Does this docstring match this code?"
is a **semantic** question no mechanical check can answer (matrix row **G —
doc-drift**). It is the first concrete use of the T2 critic seam (#87): judgment
by a model **external to the generator**.

## Contract

| Layer | Responsibility | Tested with |
|---|---|---|
| `extract_targets(source)` | documented **public** functions/methods (descends into classes, not functions) + their source | pure, stub |
| `evaluate_doc_drift(source, judge, *, required=False)` | judge each target for drift; aggregate a `CriticReport` | stub judges |
| `command_ask(command)` | turn `[critic].judge_command` into the `ask` a live judge needs (prompt→stdin, answer←stdout) | fake command |
| `55_doc_drift.sh` | run the above over `src/`, report drift | — |

- **Fail-closed** (inherited from `evaluate_rubric`): only an explicit "yes"
  passes; a judge that errors/times out is a *failed* criterion, never a silent
  pass.
- **Advisory-first:** `required=False` and the check is **not** in
  `[checks].required`, so it *reports* drift and never gates — until the model
  judge is trusted. Belongs on the CI heavy lane before a live judge runs on
  every gate.
- **Opt-in / off by default:** empty `judge_command` ⇒ the check is a no-op.

## Wiring a real judge

```toml
[critic]
judge_command = "claude -p"   # receives the prompt on stdin, replies yes/no on stdout
```

`command_ask(judge_command)` → `make_rubric_judge(...)` → a live model judge. Any
model/CLI/API-wrapper works; borromeanRings owns only the rubric and the
aggregation (the model is the module secret).

## Promotion path

1. **now** — advisory, off by default; mechanism + adapter shipped and tested.
2. **next** — enable `judge_command` on the CI heavy lane; run advisory, collect
   signal.
3. **later** — once trusted, flip `required=True` and add `55_doc_drift` to
   `[checks].required` on the heavy lane (fail-closed gating).
