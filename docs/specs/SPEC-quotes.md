# SPEC — Quote fidelity (verbatim quotation vs saved source)

**Status:** Implemented · **Realized by:** `src/meta_harness/quotes.py`,
`checks/shared/24_quotes.sh` · ADR-0065 · issue #175 (sub-issue of #172)

## Problem

The research skill promises fail-closed citations: every claim is entailed by a saved
passage under `docs/research/<slug>/` (ADR-0060). Nothing *checks* that a quotation a
document attributes to such a passage is actually the passage's text. A quote drifts when
it is paraphrased from memory, re-typed, or "cleaned up"; the document then cites a source
that says something else, and the fail-closed promise is prose, not a mechanism.

## Contract

### The marker convention

A **verifiable quotation** is a Markdown blockquote whose first non-blank following line
is a **source marker** naming a repo-relative file and a 1-based, inclusive line span:

```markdown
> Recall is the unsolved problem: the best agent misses most of the
> expert-cited sources.

— source: docs/research/deep-research/sources/3.md#L12-L13
```

Equivalent HTML-comment form (invisible when rendered):

```markdown
> Recall is the unsolved problem.
<!-- quote: docs/research/deep-research/sources/3.md#L12 -->
```

- Marker grammar: `— source: <path>#L<start>[-L<end>]` (em dash or `--`, `source:`
  case-insensitive) or `<!-- quote: <path>#L<start>[-L<end>] -->`. `<end>` defaults to
  `<start>`. `<path>` is relative to the project root, may not be absolute, and may not
  contain a `..` segment.
- The blockquote is every consecutive line beginning with `>`; a blockquote line's text is
  the line with its first `>` and at most one following space removed. Lines are joined
  with newlines, so a quote may span many lines.
- The marker must be the **first non-blank line after the blockquote**. A marker that does
  not follow a blockquote is an **orphan** and fails: a claim with no quote attached is
  never ignored.
- Fenced code blocks (```` ``` ```` or `~~~`, optionally indented) are skipped entirely: a
  marker inside one is an example, not a claim, and a fence ends any open blockquote.
- Blockquotes without a marker are ordinary Markdown (scope notes, admonitions) and are
  not checked. Only marked quotations are governed.
- A quotation is contiguous. Elision (`[...]`) is not supported: split it into two marked
  quotations.

### Normalisation (applied identically to the quote and the source span)

1. Curly quotation marks become straight: `‘` `’` → `'`; `“` `”` → `"`.
2. Every run of whitespace (spaces, tabs, newlines) collapses to one space; leading and
   trailing whitespace is removed.
3. One pair of wrapping straight double quotes is removed when the text both starts and
   ends with `"`.
4. Trailing sentence punctuation — any run of `.` `,` `;` `:` `!` `?` `…` — is removed,
   then trailing whitespace again.

Nothing else: wording, casing, internal punctuation, apostrophes and hyphens must match.

### Outcomes (per marked quotation)

| status | meaning |
|---|---|
| `verbatim` | the normalised quote occurs in the normalised source span |
| `drifted` | the source span exists but does not contain the quote; the report carries a unified diff of the raw quote lines vs the raw span lines |
| `missing` | the resolver has no such file (or the path is absolute / escapes the root) |
| `out_of_range` | the file exists but `start < 1`, `end < start`, or `end` exceeds its line count |
| `orphan` | a marker with no blockquote in front of it |

The report is `ok` only when every result is `verbatim`; it is `is_empty` when the
document carries no marker at all.

### Config

```toml
[quotes]
enabled = true          # default false ⇒ 24_quotes reports "rule off"
paths = ["docs"]        # files / directories (relative to the root) scanned for *.md
```

### Check `24_quotes` (fast lane, language-agnostic)

- `[quotes].enabled = false` (or absent) ⇒ **rule off** (a pass receipt whose log says so).
- No `*.md` under `paths`, or no marked quotation in any of them ⇒ **`noop`** (exit 3 from
  the python step), never a hollow pass (ADR-0049).
- Any non-`verbatim` result ⇒ **fail**; the log lists each one as `<doc>:<line>: STATUS
  <path>#L<a>-L<b>` (with the diff for `drifted`) and ends with the counts.
- All verbatim ⇒ **pass** with `quotes: N verbatim, 0 drifted, 0 missing, 0 out of range,
  0 orphan`.
- An unreadable document or source (exists but cannot be decoded / read) ⇒ **fail
  closed** naming the file. No network, no model call, ever.

## Edge cases

- Multi-line quote whose line breaks differ from the source's: verbatim (rule 2).
- Quote wrapped in `“ ”` in the document, unwrapped in the source: verbatim (rules 1, 3).
- Quote ends with `.` where the source line ends with `,`: verbatim (rule 4).
- Quote drops a word: drifted, with the diff.
- Span `#L5-L3`, `#L0`, or past end of file: `out_of_range`.
- Two markers after one blockquote: the second is an orphan.
- A document with a `.md` extension that is not valid UTF-8: fail closed.

## Out of scope (deliberate)

- Judging whether a passage *entails* a claim — that is the agent's job in the research
  skill's §5; this check verifies only that quoted text is the source's text.
- Fetching or re-fetching anything: the source must already be saved in the repo.
- Marking by URL: a URL is not a stable text; save the passage, cite the file.

## Design

`meta_harness.quotes` is pure: `extract(document_text)` yields the marked quotations
(`Quotation`: line, text, source path, span) and orphan markers; `normalise(text)` applies
the four rules; `verify(document_text, resolve_source, document="")` returns a frozen
`QuoteReport` of `QuoteResult`s, where `resolve_source(path) -> str | None` is injected
(`None` ⇒ missing; an `OSError` propagates so the caller fails closed); `render(report)`
formats the log. The check is thin bash mirroring `19_context_budget`: it composes the
module with `spine.load_config`, walks `[quotes].paths`, and maps exit codes to receipts.
