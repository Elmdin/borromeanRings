# ADR-0020 — Adopt the AI Fluency 4D framework as borromeanRings's collaboration vocabulary (re-authored under Apache-2.0)

**Status:** Accepted

## Context
borromeanRings already mechanizes a set of human↔agent collaboration disciplines without
naming them: the gate is automated evaluation of an agent's output, the prompt-rewrite hook
is enforced clarification of intent, and `merge.sh` is a human-vouched release boundary.
Anthropic's **AI Fluency** framework (Rick Dakan, Joseph Feller, Anthropic) gives these a
precise, externally-recognized vocabulary — the **4Ds**: Delegation, Description, Discernment,
Diligence — plus a proposed 5th, **Stewardship** (real-time governance of an autonomous run).
A set of skill notes distilled from that course was offered for inclusion.

Two problems blocked dropping those notes in directly:
1. **License.** The AI Fluency framework is **CC BY-NC-SA 4.0** (NonCommercial + ShareAlike).
   Copying its *expression* into this Apache-2.0 repo would be incompatible: ShareAlike would
   force the copied files to stay CC-licensed, and NonCommercial conflicts with permissive OSS.
2. **Accuracy & fit.** The notes misdescribed the current gate (e.g. "6 checks" — it is 8),
   referenced config that does not exist (`[hooks]`, `[post_task]`, `[post_session]`,
   `[diligence]` blocks; hooks actually live in `.claude/settings.json`), used the old
   filename `borromeo.toml`, and carried personal/portfolio material out of scope for a
   public meta-harness repo.

## Decision
Adopt the 4D (+Stewardship) vocabulary as borromeanRings's collaboration framing, and
**re-author it in our own words** rather than port the source text. Ideas and methods are not
copyrightable — only their expression is — so original text describing the same ideas is ours
to license **Apache-2.0** with the rest of the repo. The AI Fluency framework is credited as
prior art (Dakan, Feller, Anthropic) in `NOTICE` and at the top of `docs/AI-FLUENCY.md`.

Concretely (see `docs/specs/SPEC-ai-fluency.md`): one philosophy doc (`docs/AI-FLUENCY.md`,
linked from `MANIFESTO.md`) mapping the 4Ds onto borromeanRings's existing mechanisms, and
five user-level skills under `skills/` — `ai-fluency-stewardship`, `-discernment`,
`-delegation`, `-prompting`, `-diligence`. Every borromeanRings reference is verified against
the live schema; no fictional config ships.

## Alternatives considered
- **Port the notes verbatim (or lightly edited) under a CC carve-out** — rejected: introduces
  a second, NonCommercial license into an otherwise Apache-2.0 public repo (a redistribution
  and contribution hazard), and would still carry the factual errors and personal content.
- **Skip the framing entirely; keep the mechanisms unnamed** — rejected: the vocabulary is
  genuinely clarifying for contributors and costs little; naming what the gate *is* strengthens
  the project's own thesis.
- **Mechanize Stewardship now (a tripwire check/hook)** — deferred, not rejected: the
  Stewardship *skill* ships as guidance; turning its tripwires into a gated check is follow-up
  work folded into the collaboration-governance Tier C effort and the pending hook-hang fix.

## Consequences
- (+) The repo gains a principled, externally-recognized vocabulary for what it already does,
  as clean Apache-2.0 text with proper attribution — no license conflict.
- (+) Re-authoring removes all personal/conversational content and corrects every schema
  inaccuracy *by construction*; the skills describe the real gate (8 checks), real hook
  location (`.claude/settings.json`), and real filename (`borromeanrings.toml`).
- (+) Skills install user-level via `install-global.sh`, available in any governed workspace —
  consistent with `borromeanrings` / `borromeanrings-contribute`.
- (−) The framing is borrowed; borromeanRings does not own the 4D concept and must keep its
  attribution intact (NOTICE + doc header).
- (−) Five new skills are surface to maintain; kept small and consolidated (13 source files →
  5 skills + 1 doc) to limit that cost.
