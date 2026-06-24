# borromeanRings — Delayed Decisions Log

> CS130 (Part 1, L4): *"Identify decisions that need more info or are likely to change; design
> so the system does not assume a solution; keep a list of delayed decisions and track what is
> needed to resolve each."* These are the open questions from PLAN-v0 §11. The scaffold must not
> hard-code an assumption that would make any of these expensive to resolve later.

| Decision needed for scaffolding | Status |
|---|---|

## DD-1 — Coverage approach
**Question:** Confirm coverage = reported + non-regression ratchet, NOT an absolute % gate
(mutation testing deferred)?
**Default if unresolved:** ratchet only (matches QAS-7 and prior Maintainer feedback that an
absolute % is a Goodhart trap).
**What's needed to resolve:** Maintainer confirmation. Becomes ADR-0006 once confirmed.
**Design hedge:** the test check records coverage in its receipt regardless; switching to/from a
floor changes one check file, not the gate.

## DD-2 — Security tooling
**Question:** `bandit` only for v0, or also wire `semgrep`?
**Recommendation:** `bandit` only (lighter install on WSL2); add `semgrep` later when justified.
**What's needed to resolve:** Maintainer choice; confirm `semgrep` install cost is acceptable if wanted.
**Design hedge:** security is one check behind the uniform contract — adding `semgrep` is a new
`checks/` file, zero edits to `verify.sh` (QAS-3). The tool used is a *module secret*.

## DD-3 — Git initialization
**Question:** `git init` + first commit (= plan + scaffold) as part of scaffolding?
**Recommendation:** yes — so the gate, hooks, and receipt plumbing travel under version control
from commit one (supports the "failures become permanent checks" and audit principles).
**What's needed to resolve:** Maintainer go-ahead; confirm no remote/branch constraints.
**Design hedge:** none required; nothing in the design assumes git is absent or present.

---

### Resolved
- **Repo / package naming:** keep working name `borromeanRings`, Python package `meta_harness`
  (Maintainer confirmed). → captured implicitly; promote to ADR if it ever feels load-bearing.
