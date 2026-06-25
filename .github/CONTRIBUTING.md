# Contributing to borromeanRings

Thanks for your interest. borromeanRings is a **meta-harness**: a governing quality layer
that enforces engineering standards as deterministic gates. The contribution rules
below follow directly from that premise — the gate is the product, so every change
must pass it.

Read [`AGENTS.md`](../AGENTS.md) first. It states the non-obvious rules (for humans
and AI agents alike) that you could not infer from the code.

## The one rule that subsumes the rest

**You are not done until `./verify.sh` exits 0.** It runs the same gate locally that
CI runs on every PR — build, format, lint, typecheck, tests + coverage ratchet,
security, plus repo-integrity checks (git identity, layout, hygiene). Show its output
as evidence; never claim success without it.

```bash
pip install -e ".[dev]"   # one-time: install the check toolchain
./verify.sh               # exit 0 = your change is mergeable
```

Each run writes one receipt per check to `.meta-harness/receipts/<run-id>/`.

## Ground rules

- **Never weaken, disable, or bypass a check or hook to make the gate pass.**
  Integrity is the entire point. A change that games the gate is worse than no change.
- **Failures become permanent checks.** When you fix a defect, add the regression
  test/check *before* the fix, so the same defect can never silently return.
- **Plan before code for changes touching 3+ files.** Write the spec under
  `docs/specs/` and get it approved before implementing. See `PLAN-v0.md` and `docs/`.
- **Tests must meaningfully assert behavior.** Coverage is tracked and may not
  regress, but there is **no absolute coverage % target** — gaming a number is not
  the goal. Keep functions < 50 lines and files < 800 lines where it is mechanical.
- **Respect the declared layout.** `borromeanrings.toml` declares where things live
  (specs in `docs/specs/`, a fixed root-doc allowlist, grouped tests). The `07_layout`
  check enforces it.

## Commit identity

This repo declares a required commit identity in `borromeanrings.toml` (`[git]`). Commits
must use it, or the `06_git_identity` check fails closed:

```bash
git config user.name  "wimaan3"
git config user.email "imaansoltan@gmail.com"
```

## Workflow

1. Branch from `main`.
2. Make your change; add/adjust tests first where applicable (TDD: red → green → refactor).
3. Run `./verify.sh` until it exits 0.
4. Open a PR. CI runs the identical gate; it must be green to merge.

For a gated merge from a feature branch you can use `./merge.sh [base]` (runs the gate,
then merges only if green) or `./merge.sh --auto [base]` (also waits for the PR's CI).
See `docs/adr/0007-gated-explicit-merge.md`.

## Reporting bugs / requesting features

Use the issue templates under [`.github/ISSUE_TEMPLATE/`](./ISSUE_TEMPLATE). For
security issues, **do not** open a public issue — follow [`SECURITY.md`](./SECURITY.md).
