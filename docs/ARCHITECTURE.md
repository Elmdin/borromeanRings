# borromeanRings — Architecture (v0)

> CS130 framing (Part 4 §3 + Part 2 L5): start from **architectural drivers**, make quality
> attributes **measurable**, choose a **style** by its known QA trade-offs, name the **module
> secrets** (information hiding), and document the relevant **views**. The architecture *is* the
> set of structures + behavior + properties needed to reason about the system.

---

## 1. Architectural drivers

**Functional (what):** see `REQUIREMENTS.md` US-1…US-6 — one author-agnostic gate; fail-closed;
bounded retry + escalation; dangerous-command guard; auditable receipts.

**Constraints (already decided — see ADRs):** Claude Code substrate (ADR-0001); frontier API,
code leaves the machine (ADR-0002); WSL2, no GPU, no local model (ADR-0003); Python first
stack (ADR-0004).

**Quality attributes (HIGH importance + HIGH difficulty → the load-bearing walls):** integrity,
determinism/author-agnosticism, two-dimensional extensibility (checks **and** substrates),
fail-closed reliability, bounded autonomy. Formalized as QAS-1…QAS-7 in `REQUIREMENTS.md`.

---

## 2. Architectural style — a fail-closed gate over a registry of uniform-contract checks

The product is **not** a monolithic verifier; it is a **registry of independent checks** that a
**gate aggregates fail-closed**. This borrows the constraints of **Pipes & Filters** (Part 4
§3.6.1) — strict independence, agnosticism — for their QA payoff, with one deliberate difference.

| Pipes & Filters constraint | borromeanRings's analogue |
|---|---|
| **Strict independence** — filters share no state | Each `checks/NN_*.sh` shares no state with another check |
| **Agnosticism** — a filter doesn't know its neighbors | A check doesn't know which other checks exist or their order beyond its `NN` prefix |
| **Acyclic** — source → sink, no feedback | Working tree → each check → receipt; no check feeds another |
| *(difference)* transformation pipeline | borromeanRings is an **aggregation gate**: checks don't transform the artifact for the next stage; the gate ANDs their verdicts |

**QA trade-offs this buys (and costs):**

| Promoted | Inhibited / cost |
|---|---|
| **Extensibility** — add a check = drop in a file + a line in `borromeanrings.toml` (QAS-3) | **Latency** — checks run; a large suite is as slow as its slowest checks (acceptable: correctness > speed for a gate). Each check is bounded by a wall-clock `timeout` (`BORROMEANRINGS_CHECK_TIMEOUT`, default 300s) so a *hanging* tool fails closed instead of stalling the gate — see `checks/_lib.sh:borromeanrings_run_bounded`. |
| **Modifiability** — replace a check's tool without touching the gate | **No cross-check reasoning** — by design; a check can't depend on another's result |
| **Reusability** — the gate is substrate-neutral; any caller reuses it | |

---

## 3. Module secrets (information hiding — Parnas)

Per Part 2 L5: name the decisions **likely to change** and make each the **secret of one module**;
put only **stable** assumptions in interfaces.

| Secret (likely to change) | Hidden inside | Stable interface exposed | Pattern |
|---|---|---|---|
| **Which tool implements a check** (ruff/mypy/bandit; later semgrep, DD-2) | the individual `checks/NN_*.sh` | "run → exit non-zero on failure → emit a receipt" | Strategy / Single Choice |
| **Which harness/substrate drives the loop** (Claude Code today; OpenCode/Hermes later) | `.claude/hooks/*` | `verify.sh`'s exit-code contract | **Adapter** |
| **Receipt format & storage layout** | the receipt emitter (`checks/_lib.sh`) | "a receipt exists per check with status" | — |
| **The exhaustive list of expected checks** | `borromeanrings.toml` (one place only) | "every expected check emitted a pass receipt" | **Single Choice Principle** |

**The Adapter is the keystone.** `verify.sh` knows nothing about Claude Code; the `.claude/`
hooks are thin adapters translating Stop / PostToolUse / PreToolUse events into calls on the
substrate-neutral gate. *This adapter seam is what makes borromeanRings "harness-agnostic"* (QAS-4):
a future OpenCode adapter is a new directory with zero edits to `checks/` or `verify.sh`.

**Deep modules, not shallow:** `verify.sh` hides a lot (ordering, receipt aggregation, fail-closed
logic, config cross-check) behind a tiny interface (run it; read the exit code). Good ratio.

**Single Choice Principle:** exactly one place — `borromeanrings.toml` (the policy spine) — declares the full set of checks.
Adding/removing a check touches that one place plus the check file; the gate code is untouched.

---

## 4. Coupling / cohesion check

- **Coupling:** checks are mutually decoupled (no shared state, no ordering dependency beyond the
  numeric prefix). The gate depends on checks only through the receipt contract — **low coupling.**
- **Cohesion:** each check does exactly one thing (format, lint, type, test, security) — **high
  cohesion.** The gate's single concern is *aggregate-and-decide*.
- **Semantic-dependency watch (Part 2 L5):** the most dangerous coupling would be a check that
  silently assumes another ran first. The `borromeanrings.toml` required set + fail-closed-on-missing-receipt rule converts
  that latent semantic dependency into a detectable failure.

---

## 5. Views (Part 4 §3.5 / Part 1 L3)

- **Module / Code view:** `verify.sh` (gate) → `checks/_lib.sh` (receipt lib) + `checks/NN_*.sh`
  (independent checks); `.claude/hooks/*` (adapters) depend on `verify.sh`, not on checks.
- **Run-time / Component-Connector view:** the Author's harness (a deployable runtime unit) →
  invokes the hook adapter → invokes `verify.sh` → spawns each check process → checks write to the
  receipts store. A human/CI is an alternate runtime invoker of the same gate (proves QAS-2).
- **Behavioral view:** the Stop-hook loop — run gate → (pass ⇒ allow stop) / (fail & under cap ⇒
  feed back, block stop) / (fail & at cap ⇒ escalate, stop). Bounded; see US-4.
- **Data view:** receipts — per-run directory of `{check, command, exit_code, log, status}` JSON +
  the `borromeanrings.toml` required-check set. The seed of the future audit/self-assurance layer.

---

## 6. Change Impact Analysis (validating the design — Part 2 L5)

| Anticipated change | Likely? | Effort under this design |
|---|---|---|
| Swap a check's tool (bandit→semgrep) | High | 1 file (the check); gate untouched ✔ |
| Add a new check | High | 1 file + 1 line in `borromeanrings.toml` ✔ |
| Target a new harness/substrate | Medium | new adapter dir; gate + checks untouched ✔ |
| Change receipt schema | Medium | `_lib.sh` only ✔ |
| Add the external critic / config spine | Medium (deferred) | new caller of the gate; the registry pattern already supports plug-in growth ✔ |

No change is both highly likely **and** high-effort ⇒ the secrets are in the right modules.
