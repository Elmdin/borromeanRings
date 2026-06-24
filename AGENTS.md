# AGENTS.md — non-obvious rules for anyone (human or AI) working in borromeanRings

Agent-neutral on purpose, so it lifts onto other harnesses later. It states only
what you could not infer from the code.

- **The gate is `./verify.sh`. You are not done until it exits 0.** Show its
  output as evidence; never claim success without it.
- **Do not weaken, disable, or bypass any check or hook to make the gate pass.**
  Integrity is the point (precursor to tamper-evidence).
- **Failures become permanent checks.** When a defect escapes, add a regression
  test/check *before* fixing it.
- **Plan before code for changes touching 3+ files;** the human approves specs
  before implementation. See `PLAN-v0.md` and `docs/`.
- **Tests must pass and meaningfully assert behavior.** Coverage is tracked and
  may not regress — there is **no absolute coverage % target** (gaming a number
  is not the goal). Keep functions <50 lines and files <800 lines where it is
  mechanical to do so.
- **The verifier is external to the generator.** The same gate runs whether a
  human, CI, or an agent produced the change.

How to run the gate: `./verify.sh` (exit 0 = pass). Receipts for each run land
in `.meta-harness/receipts/<run-id>/`.
