#!/usr/bin/env bash
# critic-judge — a provider-agnostic, fail-closed judge for borromeanRings's T2
# critics (doc-drift, 56_critics rubric family).
#
# CONTRACT: read a rubric PROMPT on stdin, print an answer on stdout that STARTS
# WITH 'yes' or 'no'. The critics are fail-closed — only an answer beginning with
# 'y' passes; anything else (incl. this script's error/no-provider paths) fails
# the criterion. So a missing/broken judge can never silently pass a gate.
#
# ACTIVATE: set   [critic].judge_command = "bash scripts/critic-judge.sh"
# and provide a provider (below). Leave it empty to keep the critics dormant.
# See docs/CRITIC-ACTIVATION.md and ADR-0030/0036.
#
# PROVIDER (first available wins):
#   1. the `claude` CLI on PATH        → `claude -p` (natural inside Claude Code)
#   2. $ANTHROPIC_API_KEY (+ python3)   → Anthropic Messages API (stdlib urllib)
#   3. neither                          → prints 'no: ...' (fail-closed)
set -uo pipefail

prompt="$(cat)"

if command -v claude >/dev/null 2>&1; then
  printf '%s' "$prompt" | claude -p 2>/dev/null || echo "no: judge (claude CLI) failed"
elif [ -n "${ANTHROPIC_API_KEY:-}" ] && command -v python3 >/dev/null 2>&1; then
  # The prompt travels by environment, not stdin: a heredoc supplying the program
  # overrides a pipe on the same stdin, so the previous `printf | python3 - <<PY`
  # form silently delivered an EMPTY prompt to the model (shellcheck SC2259).
  BORROMEANRINGS_JUDGE_PROMPT="$prompt" python3 - <<'PY'
import json
import os
import sys
import urllib.request

prompt = os.environ["BORROMEANRINGS_JUDGE_PROMPT"]
model = os.environ.get("BORROMEANRINGS_JUDGE_MODEL", "claude-sonnet-5")
request = urllib.request.Request(  # noqa: trusted Anthropic endpoint
    "https://api.anthropic.com/v1/messages",
    data=json.dumps(
        {"model": model, "max_tokens": 256,
         "messages": [{"role": "user", "content": prompt}]}
    ).encode("utf-8"),
    headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
)
try:
    with urllib.request.urlopen(request, timeout=60) as resp:  # noqa: trusted endpoint
        print(json.load(resp)["content"][0]["text"])
except Exception as exc:  # fail-closed: any error is a 'no'
    print(f"no: judge (Anthropic API) error: {exc}")
PY
else
  echo "no: no model provider (install the 'claude' CLI or set ANTHROPIC_API_KEY)"
fi
