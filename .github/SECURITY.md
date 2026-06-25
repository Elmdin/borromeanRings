# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions, or pull requests.**

Instead, use GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab → **Report a vulnerability**
   (this opens a private advisory visible only to maintainers), or
2. Email the maintainers at **imaansoltan@gmail.com** with the details.

Please include, as far as you can:

- the affected component (e.g. a specific check, hook, or script),
- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- any suggested remediation.

We will acknowledge your report, investigate, and keep you informed of the fix and
disclosure timeline. We ask that you give us a reasonable opportunity to remediate
before any public disclosure.

## Scope

borromeanRings is a meta-harness that runs checks and hooks over a governed repository.
Security-relevant areas include, but are not limited to:

- the gate (`verify.sh`) and individual checks under `checks/`,
- Claude Code hook adapters under `.claude/hooks/`,
- the portability scripts (`init.sh`, `install-global.sh`, `merge.sh`),
- the policy spine (`borromeanrings.toml`) and its enforcement,

especially anywhere these execute shell, resolve paths, or process untrusted input.

## Supported versions

borromeanRings is at **v0** and under active development. Security fixes are applied to
the `main` branch. There are no long-term-support branches yet.
