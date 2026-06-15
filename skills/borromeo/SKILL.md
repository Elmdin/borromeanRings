---
name: borromeo
description: >
  Use borromeo (the meta-harness) in THIS workspace — set it up to govern the
  current project and operate under its gate. Use when the user says "use
  borromeo", "govern this with borromeo", or wants borromeo's enforcement in a
  new/empty project. (Installed at user level by borromeo's install-global.sh, so
  it's available in any workspace.)
---

# Use borromeo here

When invoked, set up borromeo to govern the **current workspace**, then work under it.

1. **Initialize (idempotent):** run
   `__BORROMEO_HOME__/init.sh .`
   This writes a `borromeo.toml` into the current project and installs borromeo's
   skills. If borromeo's hooks are installed globally (`~/.claude`), governance
   (the Stop gate, prompt-rewriting, the dangerous-command guard, auto-format)
   activates for this workspace as soon as `borromeo.toml` exists — no reload.
2. **Tune `borromeo.toml`** to the project: `[project].language` (python today),
   `package`/`src_dir`, `[checks].required`, `[hygiene].requires`, `[context]`.
3. **Operate under borromeo for the rest of the session:**
   - The gate is `__BORROMEO_HOME__/verify.sh`. **Do not declare a task done until
     it exits 0** — show its output as evidence (if global hooks are active, the
     Stop hook enforces this automatically).
   - For thorough web research, use the **`borromeo-research`** skill.
   - Honor borromeo's rules: don't weaken/skip checks to pass; failures become new
     checks; the verifier is external to the generator.

> Tell the user borromeo is now governing the project and what the gate command is.
