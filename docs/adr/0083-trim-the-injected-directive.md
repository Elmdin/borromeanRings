# ADR-0083 — Trim what borromeanRings injects, and pin the obligations against the trimming

**Status:** Accepted

## Context
`19_context_budget` (ADR-0055, #135) ratchets the bytes borromeanRings puts into an
agent's context on every turn. Merging the PR queue pushed the measured total past the
recorded baseline. The maintainer's decision was explicit: **trim the sources, never
re-seed the baseline** — a ratchet you move is not a ratchet.

Two findings decided the shape of this change.

**The measure was wrong before the budget was.** The reported total was 39,965 bytes
against a 32,174 baseline — a 24% regression. Most of it did not exist: `skills/<name>`
is a symlink to `.claude/skills/<name>` for two skills, and the glob counted the same
`SKILL.md` down both paths. One file on disk is one thing in an agent's context. With
the measure fixed the real overage was **220 bytes**, all of it in `stop_gate.sh`'s
message literals.

Had the number been trusted, the "fix" would have been to delete real capability to
settle a debt that was an artefact of counting one file twice.

**The directive is the highest-leverage source.** It is injected on *every prompt*,
where a skill file is loaded once per session and a hook's verdict message only on
failure. 862 bytes on every turn is the thing worth shortening.

## Decision
1. **Fix the measure first** (shipped on #162's branch): deduplicate skill files by
   `resolve()`.
2. **Tighten the prompt-rewrite directive from 862 to 690 bytes**, preserving every
   obligation: rewrite before acting; no scope the user did not ask for; the operating
   context and value priorities; the visible `Reading this as:` line; confirm-first on
   an irreversible or scope-changing reading; never pass the rewrite off as the user's
   words.
3. **Trim the Stop hook's three verdict messages** from 435 to 336 bytes. The
   fail-closed one restated itself twice.
4. **Pin the obligations with a test that asserts the imperative, not the vocabulary.**

Total: **32,123 bytes, 51 under the baseline.** Trimmed, not re-seeded.

## Consequences
- Prose that is injected on every turn is now treated as a cost, and shortening it is a
  legitimate, repeatable move rather than an edit nobody dares make.
- **The obligations are protected from the next trim.** The first version of the pinning
  test asserted `"irreversible" in directive and "confirm" in directive`. A review showed
  that still passed when the duty was downgraded to *"you may want to confirm"* — the
  vocabulary survives, the force does not. It now asserts the whole clause
  (`STOP and confirm`, the full irreversible-act list) and rejects softening hedges;
  verified by making exactly that downgrade and watching it fail.
- The directive builds its marker line from `MARKER` rather than a literal, so it cannot
  drift from `meta_harness.rewrite_contract` (#81), which decides whether a reply honoured
  the contract by looking for that exact string. `test_marker_is_the_one_the_directive_asks_for`
  now pins the marker rather than the placeholder prose around it, so a future reword is
  not a false failure while a drifted marker still is.
- A corrected negative assertion came with it: `test_directive_without_context_omits_optional_lines`
  had asserted `"account in effect"` is absent — a phrase the builder emits in *neither*
  branch, so it passed whether or not the optional line was omitted.

## Alternatives considered
- **Re-seed the baseline.** Rejected by the maintainer, and rightly: the budget exists to
  make growth visible, and a baseline that follows the measurement records nothing.
- **Cut a skill.** The largest single sources are skill files. Cutting one would have
  bought far more than 220 bytes — and would have removed capability to pay a debt that,
  once the measure was fixed, was 51 bytes on the other side of the line.
- **Stop counting hook messages.** They are emitted only on failure, so one could argue
  they are not "always-loaded" weight. Rejected: a failing gate emits them up to the
  retry cap every session, and redefining the measure to make the number go away is
  re-baselining wearing a different hat.
