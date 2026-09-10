# SPEC — Citation resolution gate

**Status:** Implemented · **Realized by:** `src/meta_harness/citations.py`,
`checks/shared/26_citations.sh` · ADR-0073

## Problem

The largest defect class this repository's review cycle found is **doc overclaim**: prose
asserting something the branch does not contain. Thirteen findings across eleven PRs.
Most of them are not judgement calls; they are path-resolution facts that a machine can
settle without asking anyone:

- a doc citing `docs/HANDOFF.md` (lands with #147) for a rule, on a base where that file
  exists only on another, still-open branch — PR #184 (twice), PR #161 (three templates),
  PR #168 (a `§2` section reference into a survey absent from that base);
- `ADR-0057` (lands with #166) and `ADR-0061` (lands with #170) cited **bare** in a table,
  on a base whose `docs/adr/` stops at 0047, while the same document labels both correctly
  elsewhere (PR #195);
- `docs/CHECKS.md` cited as one of "the two documents [that] disagree **on this base**"
  when it is not on that base at all (PR #195);
- an ADR citing issue `#53` for a fix that actually shipped in PR `#82` (PR #196);
- a SPEC contract row promising a per-check ADR citation the code never derives (PR #151).

`13_adr` (ADR-0043) already gates *that a decision was recorded*; `01_source_coherence`
(ADR-0049) already gates *that the gate is looking at real code*. This is the same shape
applied to prose: **a citation must resolve on the branch that carries it.**

## Contract

`26_citations` is off unless `26_citations` is in `[checks].required` **and**
`[citations].enabled = true`. When on, it reads the Markdown files changed on this
branch and fails if any citation in them does not resolve against this branch.

### 1. What counts as a citation (and nothing else does)

Extraction is `citations(text, base=...)` in `src/meta_harness/citations.py`. It is pure:
it never touches the filesystem, so what it recognises is decided by *shape alone*.

| Kind | Written as | Target recorded |
|---|---|---|
| `path` | a repo-rooted path token — `docs/CHECKS.md`, `src/meta_harness/spine.py:45`, `checks/shared/13_adr.sh` — in prose, in an inline-code span, or as a Markdown link target | the path, with any `#anchor` or `:line` suffix stripped |
| `anchor` | the same token with a heading fragment — `docs/CHECKS.md#enabling-checks-in-a-project` | `file#slug` |
| `adr` | `ADR-0043`, or a globbed record path `docs/adr/0043-*.md` | `ADR-0043` |
| `check` | a check id — `13_adr`, `60_mutation` | the id |

A **path token** is recognised only when all of these hold. Each condition exists to
keep an illustrative fragment from being read as a claim:

1. It has at least one `/` and its final segment carries a file extension
   (`docs/adr/` and `src/` are directories, not citations).
2. Its first segment is `.` or one of the repository's own top-level names
   (`.claude`, `.github`, `checks`, `docs`, `examples`, `scripts`, `skills`, `src`,
   `tests`, `tools`). `origin/docs/handoff` and `learn.chatgpt.com/docs/hooks` are
   therefore not citations.
3. It contains no glob or placeholder character (`*`, `?`, `<`, `>`, `{`, `}`). The one
   exception is the ADR form in the table above: a final segment `NNNN-*` under a
   directory named `adr` is a citation *to the record number*, not to a filename.

A **Markdown link target** (`[text](target)`) is a citation whenever it is repo-relative
— no `scheme:` prefix, no leading `/`, not a bare `#fragment`. Link targets are
file-relative by Markdown's own rules, so they are joined to `base` (the citing file's
directory) and normalised before being recorded; prose and code-span tokens are
repo-relative and are recorded as written. `[0001](0001-substrate-claude-code.md)` in
`docs/adr/README.md` therefore resolves against `docs/adr/0001-substrate-claude-code.md`.

### 2. What is deliberately NOT checkable, and why

Stated plainly, because a gate that implies more than it verifies is the defect this
check exists to prevent:

- **External URLs are never checked.** `https://…` in any position is skipped. Resolving
  one means a network call; this check runs on every gate and must be offline,
  deterministic, and identical on a laptop with no connectivity and in CI.
- **Issue and PR numbers (`#188`) are never checked.** Their truth lives in GitHub's
  state, which is (a) off-machine and (b) mutable after the fact. The `#53`-vs-`#82`
  defect (PR #196) is therefore *out of scope for this gate* and stays a human-review
  concern — it is included in this SPEC's problem statement to mark the boundary, not to
  claim coverage.
- **Fenced code blocks are never scanned.** Everything between triple-backtick or `~~~`
  fences is example configuration, terminal transcript, or template — illustrative by
  construction. A path inside a fence is ignored even if it looks perfect.
- **Illustrative fragments in prose or inline code are excluded by shape**, per the three
  conditions above — globs, placeholders, non-repo roots and bare directories. An
  inline-code span is otherwise scanned exactly like prose: backticks are how this
  repository writes its *real* citations, so treating them as automatically illustrative
  would exclude nearly every citation there is.
- **Whether prose *describes* the code correctly is out of scope.** That stays with
  review and the dormant `55_doc_drift` critic (ADR-0030). This check answers one
  question only: does the thing being cited exist here?

### 3. The forward-reference escape hatch, exactly

A deliberate forward reference is allowed, and only in one written form. Immediately
after the citation — optional closing backtick, then only spaces and at most one `,` or
`;` — a parenthesised label:

```text
(lands with <ref>)      (on <ref>)
```

`<ref>` is either `#<digits>` (a PR or issue number) or a branch-shaped name containing a
`/`; it may be wrapped in backticks. The keyword is matched case-insensitively; nothing
else about the form is flexible. Examples that are accepted:

- ``docs/PLUGIN.md` (lands with #166)``
- ``docs/CHECKS.md` (on `feat/self-description`)``

`(on line 5)` is not a label (no `#digits`, no `/`), and a label three clauses later in
the sentence is not a label either. The narrowness is the point: the hatch exists so an
author can say "this is not here yet, and here is where it is", and a marker that could
be produced accidentally would let the whole check be bypassed by ordinary prose.

### 4. Resolution

`unresolved(citations, resolve)` returns, in source order, every citation that has no
forward label and for which the injected `resolve(citation)` is false. `resolve` is a
parameter, not an import: the module holds no I/O and is exhaustively testable with a
dictionary.

The check supplies the real resolver, against **git-tracked** paths on this branch
(`git ls-files`), never the bare filesystem — an untracked scratch file must not be able
to satisfy a citation:

| Kind | Resolves when |
|---|---|
| `path` | the path is tracked on this branch |
| `anchor` | the file part is tracked **and** the fragment matches one of its heading slugs (`heading_slugs`: GitHub-style — lowercased, non-alphanumerics dropped, spaces to `-`) |
| `adr` | some tracked path under `[adr].dir` has a basename beginning with the four-digit number |
| `check` | some tracked `checks/*/<id>.sh` exists |

### 5. Reporting

`render(findings)` emits one line per finding, in file-then-line order:

```text
docs/EXAMPLE.md:12 — docs/HANDOFF.md — does not exist on this branch
```

### 6. Edge cases (all decided, none left to the reader)

| Situation | Behaviour |
|---|---|
| A path inside a fenced block | Ignored. |
| A citation in a file being **deleted** on this branch | Ignored — the file is not read; the branch is removing the claim, not making it. |
| No changed Markdown under `[citations].paths` | `noop` (ran, inspected nothing) — never a `pass`. |
| No merge base to diff against | `noop`. |
| A changed Markdown file that cannot be read | **fail**, naming the file. "I could not read it" is not "it was clean" (ADR-0049). |
| `git` fails inside a real repository | **fail**, closed — the same doctrine as `12_secrets` (ADR-0042). |
| `borromeanrings.toml` unreadable, or `[citations]` unparsable | **fail**, closed. A silent `noop` there would report green for a check that never ran. |
| Not a git repository at all | `noop` — there is no branch to resolve against. |

## Configuration

```toml
[citations]
enabled = true
paths = ["docs/", "README.md", "CHANGELOG.md", "skills/"]
```

`paths` are repo-relative prefixes; the default is the list above. Only `*.md` files
under them are scanned.

## Guarantees

- **Offline and deterministic** — no network, no model, no clock. The same tree gives
  the same verdict everywhere.
- **Threshold-free** — a citation resolves or it does not. There is no score.
- **Fail-closed** — unreadable config, unreadable file, or a broken git query all fail;
  none of them can present as a pass.
- **Honest about nothing** — a branch that changed no documentation reports `noop`, not
  `pass`.
- **Pure core** — `citations`, `unresolved`, `heading_slugs` and `render` are total
  functions over strings; the filesystem lives entirely in the check.
