---
name: borromeanrings-status
description: >
  Report THIS project's borromeanRings governance status — is it governed, is
  enforcement actually on (hooks wired vs. silently disabled), what did the last
  gate run say, and — the part a green verdict hides — how many of those checks
  inspected NOTHING. Single-project only; it never scans the user's other
  projects. Use when the user asks "check my borromeanRings status", "is
  borromeanRings working here", "is this project governed", "are my gates real",
  or wants to know whether a passing gate actually proved anything.
---

# borromeanRings status (this project)

Answer the question **for the project in front of you**. Never scan the user's
other projects — scope is opt-in, and a fleet-wide scan is not what was asked.

## 1. Locate the harness, then run the report

borromeanRings governs *by reference*: its code lives elsewhere and this project
points at it. Find it in this order, and stop at the first that works:

1. `$BORROMEANRINGS_HOME`, if set.
2. The hook command paths in this project's `.claude/settings.json` — they
   contain the install path (look for `stop_gate.sh`).
3. Ask the user where borromeanRings is installed.

Then run, from the project root:

```bash
"$BORROMEANRINGS_HOME/status.sh"
```

That prints the whole report. It is **read-only** — it reports the last known
state and changes nothing. Asked what the project **practises, lacks, or should
adopt next**, run `"$BORROMEANRINGS_HOME/status.sh" --swe` and answer from its
Practises / Lacks / Adopt next sections, not from memory (SPEC-swe-state.md).

## 2. Read the report honestly

Do not stop at PASS/FAIL. Three lines matter more:

| Line | What it means | When to raise it |
|---|---|---|
| `Enforcement: AUTO` | All four hooks wired — the gate runs on its own. | — |
| `Enforcement: MANUAL` / `PARTIAL` | The gate only runs when someone invokes it. Hooks may be *parked under a disabled key* — switched off deliberately at some point. | **Always tell the user.** Say what is unenforced; ask before re-enabling — turning enforcement back on is their decision, not yours. |
| `⚠ Hollow: N of M checks inspected NOTHING` | Those checks passed without looking at anything. A green resting on them proves less than it appears to. | **Always tell the user**, and name the checks. |

A verdict of PASS with a hollow count is **not** a clean bill of health. Say so
plainly rather than reporting "all green".

## 3. If checks are hollow, find out why

The usual cause is a config/reality mismatch: `[project].src_dir` or `package` in
`borromeanrings.toml` points at a path that holds no source, so every
source-reading check inspects nothing and passes.

Check it directly:

```bash
grep -E 'src_dir|package' borromeanrings.toml
git ls-files '*.py' | head          # where the code actually is
```

If they disagree, that is the bug. The `01_source_coherence` check exists to fail
the gate on exactly this — if the project does not require it yet, recommend
adding it to `[checks].required` (or running the harness's `adopt.sh`).

**Propose the fix; do not apply it silently.** Editing which checks a project
enforces changes its governance, which is the user's call.

## 4. Refresh when the last verdict is stale

The report shows the *last recorded* run. To get a current answer, re-gate:

```bash
"$BORROMEANRINGS_HOME/verify.sh"
```

This runs the real checks and writes fresh evidence. It can take a while and may
fail — that is the point. Never present a stale verdict as the current state; if
the run is old, say so or re-gate.
