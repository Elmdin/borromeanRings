# ADR-0029 — Docstring-coverage ratchet (native, non-regression)

**Status:** Accepted

## Context
API-doc coverage was unmeasured (matrix row **G**). Documentation is the first
thing to rot: a codebase that is well-documented today drifts undocumented as it
grows, with no gate to notice. The project already rejects absolute metric
targets (they get gamed) in favour of **ratchets** and meaningful signals, and
already runs a coverage ratchet for tests.

## Decision
Add check `45_docstrings` backed by `meta_harness.docstrings`: measure the
fraction of documentable definitions (module + public class/function/method) with
a docstring, and **ratchet** it against `.borromeanrings-docstring-baseline`
(non-regression, no absolute target). Native stdlib `ast` — no external tool. The
analyzer **descends into classes but not functions**, so inner closures (not
public API) are excluded. borromeanRings records a baseline of **1.0** (its public
surface is fully documented today).

## Alternatives considered
- **`interrogate` / `pydocstyle` (existing tools)** — rejected as the mechanism:
  as required tools they enlarge every governed project's footprint and can't be
  built/gated without installing them (same reasoning as ADR-0027 for
  import-linter). A ~35-line covered analyzer expresses exactly the rule we want,
  and the nested-function exclusion is trivial to control natively.
- **An absolute target (e.g. "≥ 90% docstrings")** — rejected: the project's
  standing objection to number gates (they are gamed, and "90%" is arbitrary). A
  ratchet enforces "never worse than today" without inventing a target.
- **Count nested/inner functions too** — rejected: it penalizes documented
  functions for their private closures (empirically, borromeanRings had two such
  inner callbacks); nested functions aren't public API. Classes and their methods
  still count.
- **Require docstrings on private/dunder members** — rejected: `_helper` and
  `__init__` rarely warrant prose; coverage should track the *public* contract.

## Consequences
- (+) Documentation coverage can no longer silently regress; a new undocumented
  public definition fails the gate until documented.
- (+) Zero new dependency; `docstrings.py` is pure and 100% covered; reused via
  `measure_package` for any governed Python project (opt-in via the required list
  + a baseline).
- (+) Surfacing the two undocumented inner callbacks clarified the intended
  metric (public surface, not closures) and took borromeanRings to a clean 1.0.
- (−) A ratchet at 1.0 means every new public def needs a docstring — intended,
  and the baseline can be lowered deliberately if that ever becomes wrong.
- (−) Docstring *presence*, not *quality* — a non-trivial-body rule is left as a
  future extension.
