# SPEC — Provenance gate (re-authored text must not reproduce its declared source)

**Status:** Implemented · **Realized by:** `src/meta_harness/provenance.py`,
`checks/shared/25_provenance.sh`, `[provenance]` in `spine.py` · ADR-0070 · closes #189

## Problem

ADR-0020 and epic #172 require that material ported from a CC BY-NC-SA source is
**re-authored**, never copied, into this Apache-2.0 repository. Until now the rule was
enforced by review alone. A reviewer's mechanical sweep (5- and 6-word shingle overlap
against the source, `sweep_shingles2.py`) found copied or clause-for-clause passages in two
of five ports and near-paraphrases in a third — after the builder had reported them clean.
The sweep was never committed as a check, so the next port depends on someone remembering
to run it (HANDOFF §9 rule 1).

The design obstacle: a shingle overlap **count** is a number, and this repo forbids
arbitrary numeric thresholds. The sweep also relied on a *human* to split its hits into
"generic" (a license name, a stdlib idiom) and "distinctive" (authorial phrasing). A gate
cannot make that call — any heuristic it used would be a hidden threshold. So the gate
must be **binary and about facts**, and the human classification must become a durable,
reviewable artefact rather than a judgement re-made at every review.

## Contract

### Configuration — `[provenance]` in `borromeanrings.toml`

| Key | Type | Default | Meaning |
|---|---|---|---|
| `sources` | list of paths | `[]` | Directories or files whose text must **not** be reproduced. Relative paths resolve against the project root. Read-only. |
| `paths` | list of paths | `["docs", "skills", ".claude/skills"]` | Where in **this** project the rule applies: changed files under any of these prefixes are checked. A file may be listed directly. |
| `allow` | list of strings | `[]` | The human's classification, made durable: phrases whose overlap is acknowledged as generic. Each entry is normalized exactly like the text (below). A TOML comment beside each entry records **why**; the comment is what a reviewer reads in the diff. |

Environment: `BORROMEANRINGS_PROVENANCE_SOURCES` — a colon-separated list of extra source
(a path containing a literal `:` is not supported and splits into a nonexistent entry,
which then fails closed; use `[provenance].sources` for such a path)
paths. The check reads the config first, then **appends** the environment entries. This
lets a maintainer point the check at a machine-local sibling project without committing
the path. An entry that is empty after splitting is ignored.

### Outcomes (receipt status — exactly one)

| Situation | Status | Log |
|---|---|---|
| No `[provenance]` table in the config **and** the environment variable is unset/empty | `noop` | `no [provenance] section — rule off` |
| Table present but the effective source list is empty | `noop` | `no provenance sources declared — nothing to compare against` |
| No changed file under `paths` since the merge-base | `noop` | `no changed files under <paths> since merge-base — nothing to check` |
| No base branch to diff against (`origin/dev` → `dev` → `origin/main` → `main`; first commit / detached) | `noop` | `no base branch to diff against — nothing to check` |
| A declared source path does not exist, is unreadable, or yields **zero** readable text files | `fail` | `provenance source '<path>' … — failing closed` |
| Project root is not a git repository, or `git diff` fails inside one | `fail` | `cannot list changed files … — failing closed` |
| An `allow` entry normalizes to nothing (would match everything) | `fail` | `allow entry … is empty after normalization — failing closed` |
| Every overlapping shingle is covered by `allow` | `pass` | `no unlisted 6-word overlap (…)` |
| Any overlapping shingle is **not** covered by `allow` | `fail` | one line per finding, see *Report* |

`noop` is never used to soften a computed finding: it is emitted only when the check had
nothing to compare (ADR-0049).

### Text normalization (stated exactly; applied identically to changed files, sources and `allow`)

1. The text is split into lines (`str.splitlines()`); line numbers are 1-based.
2. **Code fences are skipped**: a line whose stripped form starts with three backticks
   toggles fence state; the fence lines and every line while inside a fence contribute
   no words. (Applies to every file; a non-Markdown file simply never toggles.)
3. Each remaining line is lowercased with `str.lower()`.
4. Every character that is neither alphanumeric (`str.isalnum()`) nor whitespace is
   replaced by a space. This strips all Unicode punctuation and symbols (`—`, `“`, `*`,
   `_`, `` ` ``, `→`, …) while keeping letters in any script and digits.
5. Whitespace is collapsed: the line is split on runs of whitespace (`str.split()`),
   yielding its words.
6. The file's words are the concatenation of its lines' words; each word remembers the
   line it came from. A shingle is `n` consecutive words (default **6**) and is located at
   the line of its first word. Shingles may span lines within a file, never across files.

### Rule — `overlaps(changed, sources, allow, n=6)`

- Build the shingle set of every source file. Build the shingle list of every changed
  file (with locations).
- A changed shingle that occurs in any source file is an **overlap**.
- An overlap is **allowed** iff, for some normalized `allow` phrase `a` (a word tuple),
  `a` is a contiguous run of the shingle's words, or the shingle's words are a
  contiguous run of `a`. So a short entry (`cc by nc sa`) covers every shingle that
  contains it, and a long entry (a whole acknowledged sentence) covers every shingle
  inside it.
- **Binary verdict:** any overlap that is not allowed ⇒ `fail`. Zero unlisted overlaps
  ⇒ `pass`. There is no count, ratio, or score anywhere in the decision.
- Overlap between two changed files, or within one, is **not** a finding (self-quotes
  are the project's own text). A source file whose resolved path lies inside the project
  root is skipped for the same reason.

### Report

One line per unlisted overlap, sorted by changed path, changed line, shingle, source
path:

```
<changed_path>:<line> ↔ <source_path>:<line> — "<six words>"
```

For each (changed occurrence, source file) pair the **first** line in that source file is
reported, so a phrase repeated fifty times in the source yields one line per source
file, not fifty. The report also states the totals (findings / allowed / files compared)
so the log is self-describing. A `pass` log lists the allowed overlaps that were seen, so a
stale `allow` entry is visible.

### Changed-file selection

`git diff --relative --name-only <merge-base>...HEAD` (the 13_adr / 17_prior_art
pattern), filtered to paths under `[provenance].paths`, then to files that exist at
`HEAD` and decode as UTF-8. Committed changes only — a merge/PR-time gate.

### Source reading

Every source path is walked (files listed directly; directories recursively, skipping
`.git`, `.meta-harness`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`,
`mutants`, `node_modules`, `.venv`, `venv`). Files are
decoded strictly as UTF-8: one containing a NUL byte in its first block, or one that
fails to decode, is skipped as binary. Sources are never copied or modified, and the
receipt never carries more of a source than the overlapping six words and their location.

## Guarantees

- **Threshold-free and binary.** The decision is "does an unlisted overlap exist?" — a
  fact, not a score. The shingle size (6) is the unit of evidence, not a pass mark.
- **Human classifies, gate remembers.** The gate never guesses "distinctive". Every
  unlisted overlap fails; the human either re-authors or allowlists with a reason. The
reason is a TOML comment beside the entry, a review convention the parser cannot see:
an entry without one is caught by the PR reviewer, not by the gate. The
  allowlist is code-reviewed like everything else.
- **Fail-closed.** An absent or empty source, a git error inside a repo, or an allow
  entry that would match everything all fail. Only "nothing to compare" is `noop`.
- **No leaked paths.** Machine-local sources come from the environment; the committed
  config carries `sources = []` and is honestly `noop` on a machine without the sibling.
- **Read-only, offline.** Sources are never fetched, copied, or modified.

## Edge cases (tested)

- Planted verbatim sentence in a changed doc ⇒ `fail`, with both locations.
- The same sentence listed in `allow` ⇒ `pass`; the log names it as allowed.
- Generic phrase shorter than six words in `allow` ⇒ every shingle containing it passes.
- Overlap inside a code fence ⇒ not a finding (fence lines contribute no words).
- Punctuation and case differences between the two texts ⇒ still an overlap.
- Text shorter than six words ⇒ no shingles, no finding.
- Changed file outside `paths` ⇒ ignored.
- Binary file among sources ⇒ skipped; a source directory holding only binaries ⇒ `fail`.
- `BORROMEANRINGS_PROVENANCE_SOURCES` with `sources = []` ⇒ rule on.
