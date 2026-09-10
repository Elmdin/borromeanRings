# ADR-0064 — Predicate lint: hedge words and graph integrity in acceptance predicates

**Status:** Accepted
**Spec:** `docs/specs/SPEC-predicates.md`
**Issue:** #174 (sub-issue of #172, the 4D Fluency Compact merge)

## Context

Every SPEC in this repo ends its `Contract`/`Guarantees` section with bullets that read as
requirements, every ADR closes with `Consequences` bullets, and the issue form asks for
acceptance checkboxes. None of those is read by any gate. Two defects therefore pass review
unchallenged: a predicate with no yes/no answer ("whether the HEALTHCHECK command is
*meaningful*", "a *minimal* file", "*robust* to variance"), and a SPEC that no check, test
or issue points back to — a contract with no enforcement path. A first run of the lint over
this repo found five of the former and five of the latter.

The maintainer's 4D project had already met both defects in its `compact.yaml` validator:
a hedge-word lint over `done_when` predicates and an orphan check over the obligation
graph. Its own mutation testing exposed the orphan check as vacuous — a wildcard "traverses
everything" edge counted as a reference to every node, so no node could ever be orphaned.
Per ADR-0020 and issue #172, that project is CC BY-NC-SA and this repo is Apache-2.0, so
the *mechanism* is ported and everything — code, word list, prose — is re-authored.

## Decision

1. **A pure module, `meta_harness.predicates`.** `extract` finds predicates by this
   repo's own conventions (filename-classified: `SPEC*.md` sections named
   acceptance/contract(s)/guarantees; `NNNN-*.md` consequences bullets containing
   must/never/shall; issue-form task-list items). `hedged` names the first hedge term.
   `orphans` returns SPECs that resolve **no** shipped check id, existing test file or
   issue reference. `lint`/`render` produce the report the check logs.
2. **The hedge list is this repo's own**, organised by the ambiguity categories of
   ISO/IEC/IEEE 29148:2018 §5.2.7 and the INCOSE Guide for Writing Requirements
   (loopholes, vague qualifiers, approximations, open-ended terms, judgment calls). It is
   fixed in code and **extended** — never replaced — by `[predicates].hedges`, so a project
   cannot silently switch the rule off by emptying the list. Matching treats a hyphen as a
   word character: `best-effort` (a technical term here) is not the hedge `best effort`.
3. **Only resolvable references count** (the 4D lesson, made a rule). A check id must be
   one the governing borromeanRings ships; a test file must exist under `tests_dir`; an
   issue must be `#N`, N ≥ 1. A token that merely looks like a reference contributes
   nothing, so the orphan set is never empty by construction. The unit suite carries a
   mutation-driven test that replaces the detector with one returning nothing (and one
   returning everything) and asserts the suite's own orphan tests then fail; the heavy
   lane's `60_mutation` ratchet covers the remainder of the module.
4. **Check `23_predicates`** (shared lane, opt-in via `[predicates].enabled`): `noop` when
   off or when no predicate was found; `fail` naming `file:line — predicate — hedge` and
   listing orphan SPECs; `fail` on an unreadable file (never skip and call the rest clean);
   `pass` with counts. Registered in this repo's `[checks].required`; **not** added to
   `adopt.py`'s RECOMMENDED set — each project opts in.
5. **Issue references are syntactic.** The gate has no network, so `#N` is accepted as
   written. This is recorded as the rule's known soft spot rather than hidden.

## Alternatives considered

- **A model judge for "is this predicate checkable?"** — a T2-critic concern (ADR-0030);
  it would cost tokens on every gate and cannot be deterministic. The lint is the floor a
  deterministic gate can hold; semantic judgment stays advisory.
- **A configurable replacement hedge list** — rejected: an empty list is a silent off
  switch. `enabled = false` is the honest way to turn the rule off, and it reports `noop`.
- **Lint every list item in every markdown file** — rejected as noise: design rationale
  and problem statements are prose, not predicates. Predicate sections are named.
- **Verify issue numbers via `gh`** — rejected: no network on the gate (HANDOFF §3).

## Consequences

- (+) This repo's own contracts are now checkable statements: five hedged predicates were
  rewritten as yes/no statements (not deleted) and five orphan SPECs now name the test
  file that verifies them. The rule runs on every gate from here on.
- (+) Deterministic, native, threshold-free, honest about nothing (`noop`), fail-closed
  on unreadable input. Unit-tested to 100% line+branch coverage; integration-tested
  through the real `verify.sh` for every status.
- (−) A word list catches the common failure, not every failure: a predicate can lack a
  yes/no answer without using any listed word, and a listed word can appear in a legitimate technical sense. The fix
  for a false positive is to rephrase or, for genuinely advisory prose, move it out of
  the predicate section — never to empty the list.
- (−) Existing ADRs' `Consequences` bullets are in scope; two historical ADRs (0002,
  0047) each had one qualifier swapped for the past participle "accepted", with no reason
  or claim added. ADRs record decisions and must not be rewritten in substance — this change is
  wording only, noted here.
- (−) `#N` references are not verified against the tracker; a SPEC citing a closed or
  non-existent issue passes the orphan rule.
