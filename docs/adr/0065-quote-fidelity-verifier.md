# ADR-0065 — Quote fidelity: verbatim quotation vs saved source (`24_quotes`)

**Status:** Accepted (serves ADR-0060's verification step; part of the #172 merge)

## Context
The research skill (ADR-0014, ADR-0060) promises fail-closed citations: every claim is
entailed by a passage saved under `docs/research/<slug>/`. The *entailment* judgement is
the agent's, but one part of the promise is mechanical and was unenforced: that a quotation
the document attributes to a saved passage is actually that passage's text. Quotes drift
when re-typed, paraphrased from memory or "cleaned up", and nothing here re-checked them.

The maintainer's other project, 4D (`tools/verify_canon.py`, CC BY-NC-SA), solves the same
problem for its own corpus: every quoted string must be found, after whitespace-only
normalisation, in a raw capture kept in the repo, and the build fails otherwise. Its
license is incompatible with this Apache-2.0 repo. Both repos' ADRs (4D 0001, here
ADR-0020) chose to **port the mechanism, never copy files**.

## Decision
1. **Re-authored, not copied.** `src/meta_harness/quotes.py`, `checks/shared/24_quotes.sh`,
   the SPEC and every test are written from scratch for this repo's Markdown documents. Only
   the idea — machine re-check of quoted text against a retained source, fail the gate on
   drift — is taken; the convention, normalisation policy, outcomes, data model and report
   are this repo's own. Nothing under 4D's `canon/` was read or referenced.
2. **A minimal marker convention** (`docs/specs/SPEC-quotes.md`): a blockquote followed by
   `— source: <repo-relative path>#L<start>-L<end>` or `<!-- quote: path#L…-L… -->`. Line
   spans, not opaque source ids: the reader can open the file at the line, and the diff on
   drift is meaningful.
3. **Normalisation is stated exactly** — curly → straight quotes, whitespace collapsed, one
   wrapping `"` pair and trailing sentence punctuation removed — and nothing else. Wording,
   casing and internal punctuation must match. A quote is verbatim if its normalised text
   occurs in the normalised span.
4. **Five outcomes, all named**: verbatim, drifted (unified diff), missing, out-of-range,
   orphan (a marker with no blockquote — never ignored). Any non-verbatim result fails.
5. **Opt-in, honest, closed.** `[quotes].enabled` (default off) with `paths`; no marked
   quotation ⇒ `noop` (ADR-0049), an unreadable document or source ⇒ fail closed; the
   module is pure and does no I/O; the check does no network and no model call.
6. **Registered here now**, with `enabled = true` and `paths = ["docs"]`. Neither
   `docs/research/*.md` document has a saved source directory: `deep-research-landscape.md`
   quotes short phrases (e.g. "RAG cannot retrieve what isn't there") against URLs only, and
   `RESEARCH-SKILL-TOKEN-AUDIT.md` quotes the skill file itself. Those are **pre-existing,
   unmarked quotations** and are left as-is; the check reports `noop` for this repo until a
   research run saves sources under `docs/research/<slug>/`. The research skill's §5 now
   requires the convention for verbatim quotes in `report.md`, within its 3692 B pin.
7. `adopt.py` `RECOMMENDED` is unchanged: a project opts in per ADR-0013.

## Alternatives considered
- **Fuzzy / similarity-threshold matching** — rejected: a threshold is a number to game and
  a paraphrase is exactly the drift the check exists to catch.
- **Substring search over the whole source file, no span** — rejected: a short quote can
  match by accident anywhere, and there is no diff to show on failure.
- **Verifying against the URL** — rejected: network, non-determinism, and the passage may
  change; the saved file is the source of record (ADR-0060).
- **Checking entailment with a model judge** — out of scope; that is the agent's §5 duty and,
  if ever mechanised, an advisory critic (ADR-0030), never this gate.

## Consequences
- (+) The research skill's citation promise has a deterministic, fail-closed mechanism for
  its verbatim half; any project may adopt it for any Markdown.
- (+) A drifted quote fails with `file:line` and a diff, so the fix is obvious.
- (−) Only marked quotations are governed; unmarked blockquotes stay unverified by design.
- (−) The user-level copy of the research skill (`install-global.sh`) must be re-installed.
