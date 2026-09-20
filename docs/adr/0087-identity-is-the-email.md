# ADR-0087 — Identity is the email; the display name is not ours to require

**Status:** Accepted · 2026-09-19 · issue #229 ·
**Relates to:** ADR-0017 (git identity), ADR-0019 (local guard only on this public repo),
ADR-0049 (honest `noop`), #186 (fail-closed enumeration)

## Context

`06_git_identity` required a branch's commits to be authored by the declared `[git]`
identity, matching **both** fields. Running it on `dev` fails, and cannot be made to
pass:

```
COMMITS BY THE WRONG AUTHOR (must be wimaan3 <imaansoltan@gmail.com>):
  - Imaan <imaansoltan@gmail.com>      (x36)
```

The address is exactly the declared one. Only the display name differs, because these are
GitHub squash merges and GitHub stamps them with the account's *profile* name. Commits
are made locally with `-c user.name=wimaan3`; no local setting survives a merge performed
on someone else's server. So the check required a value this project's own merge model
cannot produce — and a check that cannot pass gets removed rather than fixed, which is
what happened: it was dropped from `[checks].required` and kept running, writing a `fail`
receipt that the verdict never mentioned (the reporting half of #229, closed by #249).

Two smaller things were wrong in the same file. The author list came from
`git log … || true`, so a git failure produced an empty list and printed "git identity
OK" over commits nobody read (#186's shape). And an undeclared identity printed
"enforcement off (pass)" — a pass for having inspected nothing, which ADR-0049 exists to
prevent.

## Decision

1. **The declared identity is the email by default.** `[git].require` takes `email`
   (default) or `email+name`. It is a closed vocabulary: an unknown value refuses the run
   the way an unknown language does, because a typo must never silently relax what is
   enforced.
2. **The rule is expressed by what the declared identity carries.** `required_identity()`
   blanks the name under `email`, and every existing rule already checks only the fields
   that are set. No rule learned a new special case.
3. **The guard follows the same requirement as the gate.** A commit the guard allows must
   not be one the gate fails. Under `email` a `-c user.name=` override is no longer
   refused; under `email+name` it still is.
4. **A git failure fails closed**, naming git's own error, instead of attributing nothing
   (#186).
5. **An undeclared identity is `noop`,** not `pass`: nothing was inspected and the count
   of checks that inspected nothing says so (ADR-0049).

## What this does not change

`06_git_identity` stays **out of this repository's** `[checks].required`. ADR-0019's
reason still holds and is not about the display name: this repo is public, and requiring
the maintainer's address would fail CI for any outside contributor's PR. What changed is
that the check now *passes* on `dev` and `main` as they exist, so its advisory line
(#249) is meaningful rather than permanently red, and a project that does control every
commit — most projects borromeanRings governs — can require it and have it work.

Flipping it on here is a one-line config change if this repo ever declares
maintainer-only commits. That is the maintainer's call, not this ADR's.

## Alternatives considered

- **Require both fields and rewrite the trunk's history.** Rejected outright: destroying
  published history to satisfy a check inverts what the check is for.
- **Require both fields and stop using squash merges.** The merge model is chosen for
  reasons (a clean trunk, one commit per reviewed change) that have nothing to do with
  identity. Trading it away for a display-name match is a bad exchange, and the name
  would still be whatever the host stamps on a merge made through the web UI.
- **Match the name case-insensitively, or ignore it when it "looks like" the same
  person.** Rejected: a fuzzy identity rule is not an identity rule. Either a field is
  required or it is not.
- **Delete the check.** It is the only thing that would catch a commit from another
  account, which is the failure it exists for. Dropping it because one field was wrong
  would discard the guarantee to avoid stating the requirement precisely.
- **Keep `pass` for an undeclared identity.** Rejected under ADR-0049: it is a pass for
  having looked at nothing, and this project's whole argument is that those must be
  visible.

## Consequences

- (+) The check passes on this project's own trunk, so it means something again.
- (+) What is being asserted is written down (`[git].require`) instead of implied by a
  string comparison over two fields.
- (+) A commit from another account still fails, which is the case that matters.
- (−) Under the default rule a wrong display name is not caught. That is the decision,
  not an oversight: the name is a profile field on another service, changeable at any
  time and rewritten by the host on merge. A project that controls its commits can
  require it.
- (−) One more config key, and one more closed vocabulary to keep in step with the docs.
