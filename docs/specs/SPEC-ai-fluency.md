# SPEC — AI Fluency collaboration skills (4D)

> Status: **proposed** (awaiting Maintainer approval). Re-authored from external
> CC BY-NC-SA course notes as original Apache-2.0 text — no source expression copied.
> See ADR-0020 (to be written on approval).

## 1. Purpose
Give agents working under borromeanRings a small, gated set of **collaboration-discipline
skills** that improve how a human directs and governs an agent *while it builds software*,
using the vocabulary of Anthropic's AI Fluency framework — the 4Ds (Delegation, Description,
Discernment, Diligence) plus a 5th, **Stewardship**. These skills mostly *name and sharpen
what borromeanRings already mechanizes* (the gate = automated Process Discernment; the
prompt-rewrite hook = Description), and add the one genuinely new mechanism: real-time
**Stewardship tripwires** for long agent runs.

## 2. Scope discipline (MANIFESTO)
borromeanRings stays narrow: *make agents build software better.* These skills are in-scope
**only as agent-direction/governance aids** — not as an AI-fluency *curriculum*, not as
end-user training, not as personal-development material. Explicitly excluded (and stripped
from the source): self-assessment baselines, fellowship/portfolio content, course-exercise
narratives, and any "learn AI fluency" coursework.

## 3. What ships (6 artifacts)
Re-authored in our own words — ideas/methods are not copyrightable, only expression is, so
writing fresh (a) removes every personal/conversational passage by construction, (b) fixes
every factual error by construction, (c) yields Apache-2.0 text we own. Every skill carries
proper YAML frontmatter (`name`, `description`) so the Skill tool can route it. Every
borromeanRings reference is verified against the **current** schema: **8** required checks
(not 6), hooks wired in `.claude/settings.json` (not in the spine), filename
`borromeanrings.toml` (not `borromeo.toml`). **No fictional config** of any kind.

| Artifact | Path | What it does | Scope-fit |
|---|---|---|---|
| 4D philosophy doc | `docs/AI-FLUENCY.md` (pointer from MANIFESTO) | Maps the 4D framework onto borromeanRings's existing mechanisms — the principled "why" vocabulary | Project documentation |
| Stewardship skill | `skills/ai-fluency-stewardship/SKILL.md` | Real-time governance of long agent runs: tripwires (retry > K, N steps with no reviewable artifact, irreversible action imminent, gate-logic edit attempt, orphaned process) → continue / interrupt / stop | Strong — agent governance |
| Discernment skill | `skills/ai-fluency-discernment/SKILL.md` | Post-run trajectory audit + output review; complements the receipt system | Strong — output verification |
| Delegation skill | `skills/ai-fluency-delegation/SKILL.md` | Authority-scope declaration + the 3 modes + 4D kickoff (absorbs the source's `scenario` skill) | Direct — scoping agent authority |
| Prompting skill | `skills/ai-fluency-prompting/SKILL.md` | The 6 techniques + pattern templates + troubleshooting table (absorbs the source's `description` + `patterns`); reference for the Description the spine already enforces | Reference — supports prompt-rewrite |
| Diligence skill | `skills/ai-fluency-diligence/SKILL.md` | Disclosure / PR-transparency checklist before sharing AI-assisted output | Direct — release responsibility |

## 4. Placement & propagation
- Skills live under `skills/` → installed **user-level** (`~/.claude/skills/`) by
  `install-global.sh` (templated + globbed alongside the existing skills), so they are
  available in any workspace borromeanRings governs — consistent with `borromeanrings` and
  `borromeanrings-contribute`. If an uninstall path enumerates skills by name, keep it
  symmetric with the new additions.
- `docs/AI-FLUENCY.md` is plain documentation; MANIFESTO gains a one-paragraph pointer to it
  (MANIFESTO stays the tight north-star doc).

## 5. License & attribution (ADR-0020)
The AI Fluency framework is **CC BY-NC-SA 4.0** (NonCommercial + ShareAlike) — incompatible
with this repo's Apache-2.0 if its *expression* were copied (SA would force CC licensing; NC
clashes with permissive OSS). Resolution: we **re-author the ideas** as original text licensed
Apache-2.0 with the rest of the repo, and **credit the framework as prior art** (Dakan, Feller,
Anthropic) in `NOTICE` and at the top of `docs/AI-FLUENCY.md`. One move resolves the license
conflict and the "no personal exposure" constraint together. Recorded in ADR-0020.

## 6. Stewardship mechanization (follow-up — NOT this spec)
The Stewardship *skill* is guidance. Turning its tripwires into a real **gated check/hook**
(retry-loop / orphaned-process detection) is deferred to the collaboration-governance Tier C
work and is the natural frame for the pending hook-hang/orphan-process fix. Tracked separately
so this spec stays docs-and-skills only.

## 7. Contract / definition of "done"
- All 5 `SKILL.md` files have valid frontmatter and load via the Skill tool; live under
  `skills/` (so `07_layout`'s root-doc rule is unaffected; this SPEC lives in `docs/specs/` ✓).
- **Zero personal/source strings:** grepping the new files for the stripped markers
  (`CCRO`, `fellowship`, `Exercise #`, personal baselines, personal-policy phrasing) returns
  nothing.
- **Zero fictional config:** no `[hooks]` / `[post_task]` / `[post_session]` / `[diligence]`
  TOML; "8 checks" not "6"; `borromeanrings.toml` not `borromeo.toml`.
- `./verify.sh` is green (8/8 required checks).
- `install-global.sh` still installs cleanly (dry check) and picks up the new skills.
- **No merge without Maintainer approval; feature branch only** (`feat/ai-fluency-skills`).

## 8. Out of scope / dropped
The source's `policy`, `plan`, and `review`-baseline skills (personal); the
`ai-fluency-borromeanrings` context skill (its value is folded into `docs/AI-FLUENCY.md`);
and all personal statements / exercise provenance. A `11_skill_anatomy` validator check for
skills is a separate, agent-skills-derived item — not part of this spec.
