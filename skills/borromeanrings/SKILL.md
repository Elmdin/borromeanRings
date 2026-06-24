---
name: borromeanrings
description: >
  Use borromeanRings (the meta-harness) in THIS workspace — set it up to govern the
  current project and operate under its gate. Use when the user says "use
  borromeanRings", "govern this with borromeanRings", or wants borromeanRings's enforcement in a
  new/empty project. (Installed at user level by borromeanRings's install-global.sh, so
  it's available in any workspace.)
---

# Use borromeanRings here

When invoked, set up borromeanRings to govern the **current workspace**, then work under it.

1. **Initialize (idempotent):** run
   `__BORROMEANRINGS_HOME__/init.sh .`
   This writes a `borromeanrings.toml` into the current project and installs borromeanRings's
   skills. If borromeanRings's hooks are installed globally (`~/.claude`), governance
   (the Stop gate, prompt-rewriting, the dangerous-command guard, auto-format)
   activates for this workspace as soon as `borromeanrings.toml` exists — no reload.
2. **Tune `borromeanrings.toml`** to the project: `[project].language` (python today),
   `package`/`src_dir`, `[checks].required`, `[hygiene].requires`, `[context]`.
3. **Operate under borromeanRings for the rest of the session:**
   - The gate is `__BORROMEANRINGS_HOME__/verify.sh`. **Do not declare a task done until
     it exits 0** — show its output as evidence (if global hooks are active, the
     Stop hook enforces this automatically).
   - For thorough web research, use the **`borromeanrings-research`** skill.
   - Honor borromeanRings's rules: don't weaken/skip checks to pass; failures become new
     checks; the verifier is external to the generator.

> Tell the user borromeanRings is now governing the project and what the gate command is.
