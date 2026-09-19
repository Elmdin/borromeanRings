# SPEC — Config/policy spine (Layer 1)

> Status: spec for the first iteration of the spine. Approved approach: config = `borromeanrings.toml`;
> start with the required-check set + declared context; designed so prompt rewriting plugs in next.

## 1. Purpose
A single declarative source of the **invariants this repo must always satisfy**. Declared once in
`borromeanrings.toml`, enforced on **every** gate run. This generalizes v0's hard-coded `manifest.json` check list under `checks/` +
receipts into a real spine — the seed of the §11 self-assurance layer ("every declared requirement
has an executed-and-passed receipt").

## 2. Two principles this spine must honor (from the Manifesto + recent clarifications)
- **Enforce outcomes, preserve agent autonomy.** The spine checks *results against declared policy*
  (gates + config-compliance). It must **not** constrain *how* the wrapped agent/harness plans or
  decides — many harnesses plan better than borromeanRings would. borromeanRings governs the *what* (invariants
  on outcomes), never the agent's *thinking*.
- **Declared context fuels prompt rewriting (the next build).** The spine holds the operating
  context (account, value priorities, requirements). Prompt rewriting — performed by the *wrapped
  agent*, not borromeanRings — consumes this so the user's in-the-moment prompt is improved while
  preserving intent, per best agentic + SE practices and the current context. borromeanRings *enforces
  that this happens well*; it does not do the rewriting itself.

## 3. Config schema (`borromeanrings.toml`)
```toml
[checks]
required = ["00_build", "10_format", "20_lint", "30_typecheck", "40_test", "50_security"]

[context]                 # declared once; surfaced to the agent (e.g. for prompt rewriting)
account = "3MagicLabs/borromeanrings"
value_priorities = ["correctness", "security", "maintainability", "performance"]
```

## 4. Contract
- `meta_harness.spine.load_config(path="borromeanrings.toml") -> Config` with
  `Config(required_checks: tuple[str, ...], context: Mapping[str, Any])`.
- **Fail-closed:** if `[checks].required` is empty/absent, `load_config` raises — no declared checks
  is a misconfiguration, never "nothing to enforce so pass."
- `verify.sh` reads the required set from the spine (replacing that `manifest.json` as the single
- **Legacy name (deprecated, issue #62):** `resolve_config_path` — when the canonical
  `borromeanrings.toml` is absent and a sibling pre-rename `borromeo.toml` exists, that file
  loads instead with a `FutureWarning` on stderr — that category is shown by Python's default
  filters from any module (a `DeprecationWarning` is not, outside `__main__`), once per process
  per legacy file (the canonical file always wins when present; any other file name is never
  redirected). `verify.sh` and the hooks accept either name so an already-governed project never
  silently falls out of governance. Migration: `docs/RENAME.md`.
- `verify.sh` reads the required set from the spine (replacing the former per-check manifest as the single
  source — Single Choice Principle) and enforces config-compliance: every required check must have a
  pass receipt.

## 5. Test plan
`tests/unit/test_spine.py` (keeps coverage at the ratchet baseline):
- valid config → correct `required_checks` + `context`
- empty/absent `[checks].required` → raises (fail-closed)
- absent `[context]` → empty mapping (no crash)

## 6. Deferred (next iterations)
- **Prompt rewriting** consuming `[context]` (the immediate next build).
- Richer enforced constraints (e.g. forbidden patterns, required files, account/identity checks).
- Per-project / per-harness config layering; config-compliance diffing + tamper-evidence.
