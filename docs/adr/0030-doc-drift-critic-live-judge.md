# ADR-0030 — Doc-drift: the first live application of the T2 critic seam

**Status:** Accepted (extends ADR-0023)

## Context
ADR-0023 shipped the critic as a *seam* — a deterministic, fail-closed harness
around an injected judge — but wired to nothing, so it enforced nothing. The
first concrete question worth judging is **doc-drift**: `45_docstrings` proves a
docstring *exists*; only a semantic judge can tell whether it still *matches the
code*. This is the first step of the seam's stated promotion path (seam →
advisory → gating).

## Decision
Add `meta_harness.doc_drift` and the advisory check `55_doc_drift`:
- **Pure core** — `extract_targets` (documented public functions/methods) and
  `evaluate_doc_drift` (judge each against the single drift question, aggregate a
  `CriticReport`). Unit-tested with stub judges; no model, no network; 100%
  covered.
- **Live-judge adapter** — `command_ask(command)` turns the operator-declared
  `[critic].judge_command` into the `ask(prompt)->answer` that
  `make_rubric_judge` needs. That is the "real model judge": prompt on stdin,
  yes/no on stdout; any model/CLI/API-wrapper plugs in.
- **Advisory-first & opt-in** — `required=False`, the check is **not** in
  `[checks].required`, and it is a no-op unless `judge_command` is set. It reports
  drift; it never gates yet.

## Alternatives considered
- **Gate on it immediately (required, fail-closed)** — rejected: a
  non-deterministic model call must not sit on the fail-closed verdict until it
  has earned trust (the seam's whole doctrine). Advisory-first collects signal
  without risking false gate failures.
- **Call an API/SDK directly from Python (hardcode a provider)** — rejected:
  breaks model-agnosticism and needs a dependency + key management. A declared
  `judge_command` keeps the model a swappable module secret and needs no new
  dependency (just stdlib `subprocess`).
- **Run the judge inside the fast Stop gate** — rejected: a model call per
  function on every Stop is far too slow/networked; doc-drift belongs on the CI
  heavy lane. Shipped off-by-default so it never burdens the fast gate until
  deliberately enabled there.
- **`shell=True` for the judge command** — rejected: `shlex.split` + `shell=False`
  avoids shell-injection surface; the two remaining bandit findings (B404/B603)
  are suppressed with justification (the command is trusted repo config, not
  external input).

## Consequences
- (+) The critic seam now has a real, tested application; doc-drift is detectable
  the moment a judge command is declared.
- (+) The live-judge adapter (`command_ask`) is reusable for every future critic
  check (test-smell, boundary-value, naming, …) — they differ only in rubric.
- (+) Model-agnostic and dependency-free; deterministic aggregation stays
  unit-testable.
- (−) On borromeanRings it is dormant (`judge_command` empty) until the heavy lane
  lands — shipped mechanism, not yet live enforcement (honestly advisory).
- (−) `subprocess` in the package required two justified `# nosec` suppressions.
