---
name: Bug report
about: Report a defect in borromeanRings (the gate, a check, a hook, or a script)
title: "[bug] "
labels: bug
assignees: ''
---

<!-- Security issue? Do NOT file it here. See .github/SECURITY.md. -->

## What happened

A clear description of the bug.

## Expected behavior

What you expected the gate / check / script to do instead.

## Reproduction

Steps to reproduce:

1. ...
2. ...

If a check misbehaved, attach the relevant receipt from
`.meta-harness/receipts/<run-id>/` and the `./verify.sh` output.

## Environment

- borromeanRings commit / branch:
- OS:
- Python version:
- Governing this repo, or a target project (via `init.sh`)?

## Notes

Per borromeanRings's own rule, a confirmed defect should become a permanent regression
check before it is fixed. Mention if you have a failing test that reproduces it.
