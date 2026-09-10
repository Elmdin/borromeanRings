# ADR-0069 — Multi-harness substrates: one gate, one hook set, per-substrate wiring adapters

**Status:** Accepted (decision only — no adapter is built by this ADR; phase 1 is #194, on an
explicit go) · 2026-09-10 · research epic #142 ·
**Spec:** `docs/specs/SPEC-substrate-adapter.md` ·
**Survey:** `docs/research/HARNESS-SUBSTRATES.md`

## Context

borromeanRings's guarantee is delivered through six Claude Code hooks (`docs/HOOK-EVENTS.md`)
that are, by design, thin adapters over a substrate-neutral gate (`verify.sh`; ADR-0001,
ADR-0005, ADR-0013). No second substrate has ever been wired, so the seam is asserted, not
proven. Issue #142 asks what a second substrate would need and which one to pick.

The survey read the public documentation of six other harnesses (2026-09-09/10) and found:

- **Codex CLI** exposes the same six events under the same names, the same stdin envelope,
  the same exit-0 / exit-2-with-stderr semantics, the same `permissionDecision: deny` and
  `additionalContext` outputs, and a `SessionStart` with `source: compact`.
- **Gemini CLI** carries all six under different names, with an async advisory `PreCompress`
  and no `compact` source on `SessionStart`.
- **OpenCode** and **Cline** have the events as in-process JS/TS functions with no
  stdin/stdout contract; OpenCode documents no prompt-submit hook and no way to block a turn.
- **Hermes** has shell hooks with a documented "Claude-Code compatible" output form, no
  pre-compaction hook, no context injection at session start, and a history of documenting
  hooks before they fired.
- **Aider** has no hook surface at all (only `--lint-cmd`/`--test-cmd`) and has not released
  in thirteen months; **Roo Code** is archived.

Three constraints do not bend (HANDOFF §3): per-project opt-in, governance by reference
(nothing copied into the governed project), and hooks inert outside a governed project.

## Decision

1. **One gate, one hook set.** `verify.sh`, `checks/`, `src/meta_harness` and the six
   scripts in `.claude/hooks/` are the *only* implementation, on every substrate. The
   contract they already implement (JSON on stdin → decide → JSON or text on stdout →
   exit 0/2) is written down in the spec §1 and becomes the thing adapters conform to.
2. **Per-substrate wiring adapters** live under `adapters/<substrate>/` and hold **only
   wiring**: a `manifest.json` declaring which of the six events the substrate carries and
   in what mode (`full` / `degraded` / `absent`), the substrate's native registration file,
   thin shims that translate payload in and output out and then exec the script in place,
   and one fixture per carried event. Never a second copy of a hook, a check or the gate — a
   conformance test enforces it.
3. **Degradation is declared, never silent.** Where a substrate cannot carry an event, the
   spec §4 names the fallback (no pre-compact ⇒ the brief is re-injected at session start
   only; no deny primitive ⇒ the guard becomes detect-only with the gate as backstop; no stop
   hook ⇒ enforcement is `MANUAL`, CI only), and self-status reports the substrate's coverage
   from the manifest. This extends ADR-0049's "honest about nothing" from checks to hooks.
4. **A conformance test is the definition of done for any adapter** (spec §5): inbound and
   outbound fidelity through recorder/stub scripts, inertness, no-second-copy, manifest
   honesty, and the ADR-0025 adversarial corpus yielding the same accept/deny set.
5. **Phase-1 target: Codex CLI** — filed as **#194** with acceptance criteria drawn from the
   conformance test. Reason: its hook contract is a near-copy of ours, so the adapter is close
   to the identity and proves the seam with the least translation to get wrong; it is
   actively released (0.154.0, 2026-09-09) and Apache-2.0. Gemini CLI is the runner-up (all
   six, but renamed events, millisecond timeouts and two degraded events). Building #194 still
   requires the demand test in #142 AC 1 — a governed project actually using Codex — not
   popularity.

## Alternatives considered

- **Fork the hooks per substrate** (`.codex/hooks/stop_gate.sh`, `.gemini/hooks/…`) —
  rejected. Six scripts × N substrates drift immediately; the dedupe, bounded-read and
  fail-open/closed decisions in `_lib.sh` and `stop_gate.sh` were each fixes for real
  incidents (PR #82, the orphaned-shell bug) and would have to be re-fixed N times. It is also
  the "copy" model ADR-0013 rejected, one level up.
- **A governance daemon every substrate talks to** (a local server; substrates send events
  over a socket/HTTP; the daemon runs the hooks) — rejected for now. It adds a long-running
  process, a port (the safety rule is bind-127.0.0.1-only, and a daemon is one more thing to
  leave running), a second protocol to specify and version, and a new failure mode (daemon
  down ⇒ hooks silently absent — precisely the vacuity this project exists to prevent). Every
  surveyed substrate with a hook surface can already spawn a process, so a daemon buys
  nothing today. Revisit only if an in-process substrate (OpenCode, Cline) cannot spawn
  scripts within its timeout.
- **Do nothing; stay Claude-Code-only** — rejected as the *permanent* answer, accepted as the
  *current* one: nothing is built until a governed project needs it (ROADMAP Phase 2). But
  the seam's contract was undocumented and its degradation rules undecided, which made the
  eventual cost unknown; this ADR fixes the price without paying it.
- **Standardise on the Claude Code hook JSON as "the" contract and require substrates to
  emit it** — partly adopted: the spec §1 *is* that contract, and Codex's near-identity shows
  it is a reasonable lingua franca (Hermes even accepts the `{"decision": …}` form). But
  substrates will not change for us, so the shim, not the substrate, does the translating.

## Consequences

- (+) The adapter seam is now a written contract with a test, not a comment in a script.
  Any future hook change must keep §1 true or update it and the adapters together.
- (+) `verify.sh` and the six scripts stay byte-identical across substrates; the adversarial
  corpus and every existing hook test remain the evidence for all of them.
- (+) Self-status can say, per substrate, what is enforced and what is not — the hollow-green
  hazard of "hooks installed, three of them never fire" is reported instead of hidden.
- (−) `CLAUDE_PROJECT_DIR` is a Claude-Code-named variable read by every hook. Renaming it
  would touch the scripts this ADR promises not to fork; shims export it from `cwd` instead.
  Accepted as a naming wart.
- (−) Post-tool on Codex is degraded (`apply_patch` carries a patch, not `file_path`); the
  format check catches drift at the gate, at the cost of a possible extra retry.
- (−) Documentation of these harnesses changes weekly; the survey is dated and the manifest
  carries `docs_read_on`. An adapter that lands re-reads its docs that day.
- (−) Aider and Roo Code cannot host the gate as a hook; the survey says so rather than
  promising a degraded adapter. Aider users can run `verify.sh` as `--test-cmd` and get CI
  enforcement — `MANUAL` in self-status terms.
- (−) The survey could not verify Cline's hook wire contract from its documentation and
  could not reconcile the release date its releases page returned; Cline stays `unverified`
  until a fixture proves an event fires.
