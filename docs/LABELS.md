# Labels and milestones

The label and milestone scheme for this repository. It is the vocabulary
[`TRIAGE.md`](TRIAGE.md) uses; this file is the reference, that one is the procedure.

The labels below are what GitHub **should** have. [`scripts/labels.sh`](../scripts/labels.sh)
makes it so (`--dry-run` to preview). It is run by a human, on purpose — label changes
are outward-facing, so no hook or workflow runs it.

## Conventions

- **Names are flat, not prefixed**, except `priority:`. The scheme predates any
  `type/`, `area/` convention and every open issue already uses these names; renaming
  would break `TRIAGE.md`, saved searches, and the closed history for no gain.
- **Exactly one type label** per issue (plus `epic` when it is a tracker).
- **Exactly one priority.** Missing priority means "not yet triaged", not "low".
- **Status labels are transient.** They say what the issue is waiting on and are
  removed when it stops waiting.

## Type — what kind of work is it?

| Label | Colour | Meaning |
|---|---|---|
| `harness-feature` | `#5319E7` | A new borromeanRings capability, usually a new check or command |
| `bug` | `#d73a4a` | Something does not do what it says it does — including a check that passes without inspecting anything |
| `quality` | `#1d76db` | Engineering rigor on what exists: tests, lint, verification |
| `security` | `#b60205` | Hardening, or a vulnerability in the harness itself (report vulnerabilities privately first — `SECURITY.md`) |
| `efficiency` | `#fbca04` | Token/compute cost reduction that does not cost output quality |
| `research` | `#d4c5f9` | Investigation and prior-art synthesis, producing a written decision |
| `evaluation` | `#c5def5` | Assessing how the platform works and what to improve |
| `documentation` | `#0075ca` | Docs, specs, contributor material |
| `repo-setup` | `#bfdadc` | GitHub settings, repo hygiene, scaffolding |
| `deep-research` | `#0E8A16` | The research *enhancement* — a harness feature, not the separate product |
| `epic` | `#3e4b9e` | Tracking issue spanning several work items; add alongside a type |

## Priority — what happens if it waits?

| Label | Colour | Meaning |
|---|---|---|
| `priority:high` | `#d93f0b` | Blocks a milestone, or leaves a gate that can be trusted when it should not be. A hollow guarantee is always high |
| `priority:med` | `#fbca04` | Real value, no one is blocked |
| `priority:low` | `#c2e0c6` | Worth doing; nothing breaks if it never happens |

## Status — what is it waiting on?

| Label | Colour | Meaning |
|---|---|---|
| `needs-triage` | `#ededed` | Filed through a form, not yet given a type/priority/milestone. Applied automatically by the issue forms; removed at triage |
| `needs-spec` | `#fef2c0` | Touches 3+ files; a spec under `docs/specs/` must be written and approved before code |
| `needs-adr` | `#fef2c0` | Adds/removes a gate or changes the trust model; an ADR is required (`TRIAGE.md` §5) |
| `blocked` | `#000000` | Cannot proceed until a named issue/PR lands — say which in a comment |

## Scope and resolution

| Label | Colour | Meaning |
|---|---|---|
| `separate-product` | `#BFD4F2` | Belongs to a product built *with* borromeanRings, not the harness; closed here with a pointer |
| `duplicate` | `#cfd3d7` | Already tracked — link the original when closing |
| `wontfix` | `#ffffff` | Deliberately not doing this; the closing comment says why |
| `invalid` | `#e4e669` | Not actionable as written |

## Community

| Label | Colour | Meaning |
|---|---|---|
| `good first issue` | `#7057ff` | Self-contained, gate-checkable, no trust-root code |
| `help wanted` | `#008672` | Maintainer would welcome an outside PR |
| `question` | `#d876e3` | Needs an answer, not a change |

### Retained GitHub default

| Label | Colour | Meaning |
|---|---|---|
| `enhancement` | `#a2eeef` | GitHub's default. **Do not apply to new issues** — the feature form uses `harness-feature`. Kept only so existing issues carrying it stay searchable |

## Milestones

Milestones are questions, not dates. Leave one empty rather than guess
(`TRIAGE.md` §4). They exist on GitHub already; the script does not touch them.

| Milestone | Question it answers |
|---|---|
| **M1 Pre-public hardening** | Is this safe and presentable to strangers? |
| **M2 Platform evaluation & quality** | Does the platform actually do what it claims? |
| **M3 Research & efficiency** | Can it do the same for less? |
| **M4 Docs & community** | Can someone else contribute to it? |

## Changing the scheme

Edit the tables here **and** the array in `scripts/labels.sh` in the same PR, then a
maintainer runs the script. The script only creates and updates; it never deletes a
label, so retiring one is a manual, deliberate act.

> Before the issue forms go live, run `scripts/labels.sh --dry-run` then `scripts/labels.sh`: `needs-triage`, `needs-spec`, `needs-adr` and `blocked` do not exist on GitHub yet, and GitHub drops unknown labels silently. All four are created by the script.
