# Testing borromeo's full feature set (new Claude session + new project)

A reproducible walkthrough to exercise every borromeo capability on a fresh project.
borromeo governs *by reference* — its code stays put; the target just points at it.

## 0. Prereqs
- borromeo cloned somewhere (call it `$BORROMEO` = its path).
- Python ≥ 3.11 with the check tools: `pip install ruff mypy pytest pytest-cov bandit`
  (or use borromeo's `Dockerfile`).
- A **Python** target project (checks are Python-only today).

## 1. Make a small target project
```bash
mkdir -p ~/demo/src/app ~/demo/tests
printf '# demo\n' > ~/demo/README.md
cat > ~/demo/pyproject.toml <<'EOF'
[project]
name = "app"
version = "0.0.0"
requires-python = ">=3.10"
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
[tool.coverage.run]
source = ["src"]
branch = true
EOF
: > ~/demo/src/app/__init__.py
printf 'def add(a: int, b: int) -> int:\n    return a + b\n' > ~/demo/src/app/core.py
printf 'from app.core import add\n\n\ndef test_add() -> None:\n    assert add(2, 3) == 5\n' > ~/demo/tests/test_core.py
```

## 2. Install borromeo into the target (by reference)
```bash
"$BORROMEO/init.sh" ~/demo
# edit ~/demo/borromeo.toml: set [project] package = "app"
```
This writes `borromeo.toml` + `.claude/settings.json` (hooks → `$BORROMEO`) and installs the
**borromeo-research** skill into `~/demo/.claude/skills/`.

## 3. Open a NEW Claude Code session in the target
```bash
cd ~/demo && claude
```
The hooks are now active for the agent prompted **in this project**.

## 4. Exercise each feature

| Feature | How to test | Expected |
|---|---|---|
| **Gate (green)** | `"$BORROMEO/verify.sh"` (from `~/demo`) | all 7 checks PASS |
| **Gate (bites)** | edit `src/app/core.py` → `return "oops"`; re-run | `30_typecheck` + `40_test` FAIL |
| **Stop hook** | in the session, have the agent leave that bug and try to finish | it's **blocked**: "borromeo gate FAILED (attempt 1/3)…" until fixed |
| **Prompt rewriting** | submit any prompt | a `[borromeo]` rewrite directive is injected (agent shows the rewrite) |
| **Dangerous-command guard** | ask the agent to run `rm -rf /` | **denied** with a reason |
| **Auto-format** | have the agent edit a `.py` | it's `ruff format`-ed automatically (PostToolUse) |
| **Hygiene gate** | `rm ~/demo/README.md`; re-run the gate | `05_hygiene` FAILS (declared artifact missing) |
| **Config spine** | edit `~/demo/borromeo.toml` `[checks].required` / `[hygiene].requires` | the gate enforces exactly what's declared |
| **Research skill** | ask the agent to *"research <topic> with borromeo"* (invokes `borromeo-research`) | it shows a steerable search **plan**, runs many query mutations across engines, synthesizes, and **verifies each claim against its source** (fail-closed), visibly |

## 5. What is NOT yet portable (honest caveats)
- **`merge.sh`** (gated/auto merge) is borromeo-self-oriented — not wired for arbitrary targets yet.
- **Branch protection** (server-side required check) needs GitHub Pro/Team or a public repo (ADR-0009).
- **Checks are Python-only** — JS/Go/etc. need their own checks behind the same contract.
- The research skill is **Claude-Code-shaped**; on other harnesses it'd need an adapter.

## 6. Run borromeo's own gate (sanity check)
```bash
cd "$BORROMEO" && ./verify.sh    # borromeo governs itself; should be green
```
