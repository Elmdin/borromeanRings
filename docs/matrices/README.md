# Governance matrices — index

`docs/ENFORCEMENT-COVERAGE.md` §2 is matrix **#1's sibling**: the code-quality axis (rows A–K).
§6 of that document lists the **six governance axes** and their one-word status; this
directory holds the full matrix behind each §6 row. `describe.sh` (#132) reads the §6 table,
never these files, so §6 stays the machine-readable summary and these are the detail.

| # | Matrix | Document | §6 status |
|---|---|---|---|
| 1 | AI-agent quality | *(not yet a document — its rows live in §6 and ADR-0037; #135 and the agent-only rule in ADR-0030 shape it)* | partial |
| 2 | Security & compliance | [`02-security-compliance.md`](02-security-compliance.md) | documented |
| 3 | Delivery / DORA | [`03-delivery-dora.md`](03-delivery-dora.md) | documented |
| 4 | Operational / SRE | [`04-operational-sre.md`](04-operational-sre.md) | documented |
| 5 | Data / ML | [`05-data-ml.md`](05-data-ml.md) | documented |
| 6 | Product / UX | [`06-product-ux.md`](06-product-ux.md) | documented |

## Conventions (every matrix uses the same table)

| Column | Meaning |
|---|---|
| **Row** | Stable id (`S1`, `D1`, `O1`, `M1`, `U1`, …) so issues and ADRs can cite a row. |
| **Criterion** | The practice, phrased as something a gate can decide. Every criterion is **binary** (present / absent, violation / none) or a **threshold-free ratchet** (may not regress vs a recorded baseline). No percentages, no scores, no "≥ N" targets — see `docs/HANDOFF.md` §3 "Threshold-free". |
| **Enforced by** | The check id (`checks/<lane>/<id>.sh`) or hook that enforces the row **today**, verified by reading the script — or `gap → #issue`, the issue that would close it. A check is only named if the script actually decides that criterion. |
| **Buildability** | `now` — deterministic from git/text, buildable without new inputs · `telemetry` — needs CI/deploy/runtime data the gate does not have · `archetype` — needs the project to declare its kind (#79) before the row can be non-`noop`. |
| **Source** | A real, checkable reference for the criterion (standard, book chapter, paper, spec). |

A row marked `archetype` is wired to #79: an archetype declaration (`[project].kind`) is what
turns a row from "not applicable, `noop`" into "required, must be non-`noop`" — the mechanism
described in #130 and #138.

## Status vocabulary in §6

- **partial** — rows are known and some are shipped, but no document maps every row.
- **documented** — a document here maps every row to a check or to a gap with an issue.
- The word is free text to `describe.py`; it is rendered, not validated. Keep it one word.

## How a row graduates

Exactly as `docs/ENFORCEMENT-COVERAGE.md` §4: spec → branch → passes the gate → human-approved
merge, landing at the lowest tier that expresses it (T0 gate > T1 ratchet > T2 critic > T3
advisory). When a row lands, update **both** the matrix document and the §6 status word in the
same PR — drift between the two is the defect #132 exists to catch.

## Sub-issues (one per matrix)

- #155 security (S15)
- #156 delivery/DORA (D9–D13)
- #157 SRE (O9, O10, O12, O14, O15)
- #158 data/ML (M3, M13–M15)
- #159 product/UX (U4–U9, U18)
- #154 `15_a11y` reports `pass` instead of `noop` on no HTML
