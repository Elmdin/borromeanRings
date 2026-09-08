"""Context-budget measurement (ratcheted by 19_context_budget). ADR-0055."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from meta_harness.context_budget import (
    BYTES_PER_TOKEN,
    ContextBudget,
    ContextSource,
    estimate_tokens,
    format_report,
    hook_message_bytes,
    measure_context_budget,
)


def test_bytes_per_token_is_the_documented_approximation() -> None:
    assert BYTES_PER_TOKEN == 4


@pytest.mark.parametrize(
    ("n_bytes", "tokens"),
    [(0, 0), (1, 1), (3, 1), (4, 1), (5, 2), (8, 2), (9, 3), (4000, 1000), (4001, 1001)],
)
def test_estimate_tokens_rounds_up(n_bytes: int, tokens: int) -> None:
    assert estimate_tokens(n_bytes) == tokens


def test_estimate_tokens_rejects_negative_bytes() -> None:
    with pytest.raises(ValueError, match="negative"):
        estimate_tokens(-1)


def test_hook_message_bytes_counts_only_echo_and_printf_literals() -> None:
    script = (
        "#!/usr/bin/env bash\n"
        'echo "hello"\n'  # 5
        "  printf 'ab %s\\n' \"$x\"\n"  # 7 — the first literal only
        'x="not a message"\n'  # assignment: not counted
        "echo $var\n"  # unquoted: nothing literal to count
        '{ echo "in a block" >&2; }\n'  # not at line start: not counted
        "  echo 'tail'\n"  # 4
    )
    assert hook_message_bytes(script) == 5 + 7 + 4


def test_hook_message_bytes_empty_script_is_zero() -> None:
    assert hook_message_bytes("") == 0
    assert hook_message_bytes("set -uo pipefail\nexit 0\n") == 0


def test_hook_message_bytes_counts_utf8_bytes_not_characters() -> None:
    assert hook_message_bytes('echo "é"\n') == 2


def test_context_source_and_budget_are_immutable() -> None:
    src = ContextSource(kind="skill", path="skills/a/SKILL.md", bytes=8, tokens=2)
    with pytest.raises(FrozenInstanceError):
        src.bytes = 9  # type: ignore[misc]
    budget = ContextBudget(sources=(src,), total_bytes=8, total_tokens=2)
    with pytest.raises(FrozenInstanceError):
        budget.total_bytes = 0  # type: ignore[misc]


def test_measure_empty_project_has_no_sources(tmp_path: Path) -> None:
    budget = measure_context_budget(tmp_path)
    assert budget == ContextBudget(sources=(), total_bytes=0, total_tokens=0)
    assert budget.is_empty is True


def test_measure_directive_only(tmp_path: Path) -> None:
    budget = measure_context_budget(tmp_path, directive="12345678")
    assert budget.sources == (
        ContextSource(kind="directive", path="<prompt_rewrite directive>", bytes=8, tokens=2),
    )
    assert budget.total_bytes == 8
    assert budget.total_tokens == 2
    assert budget.is_empty is False


def test_measure_every_source_kind_in_a_stable_order(tmp_path: Path) -> None:
    files = {
        "AGENTS.md": "a" * 12,
        "CLAUDE.md": "c" * 5,
        "skills/zeta/SKILL.md": "z" * 9,
        "skills/alpha/SKILL.md": "a" * 4,
        ".claude/skills/status/SKILL.md": "s" * 6,
        ".claude/hooks/stop_gate.sh": 'echo "gate FAILED"\n',  # 11
        ".claude/hooks/_lib.sh": "borromeanrings_claim() { :; }\n",  # 0 → omitted
        "skills/alpha/README.md": "not a skill file",  # ignored
    }
    for rel, content in files.items():
        dest = tmp_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    budget = measure_context_budget(tmp_path, directive="d" * 7)

    assert budget.sources == (
        ContextSource(kind="directive", path="<prompt_rewrite directive>", bytes=7, tokens=2),
        ContextSource(kind="instructions", path="CLAUDE.md", bytes=5, tokens=2),
        ContextSource(kind="instructions", path="AGENTS.md", bytes=12, tokens=3),
        ContextSource(kind="skill", path="skills/alpha/SKILL.md", bytes=4, tokens=1),
        ContextSource(kind="skill", path="skills/zeta/SKILL.md", bytes=9, tokens=3),
        ContextSource(kind="skill", path=".claude/skills/status/SKILL.md", bytes=6, tokens=2),
        ContextSource(kind="hook", path=".claude/hooks/stop_gate.sh", bytes=11, tokens=3),
    )
    assert budget.total_bytes == 7 + 5 + 12 + 4 + 9 + 6 + 11
    assert budget.total_tokens == 2 + 2 + 3 + 1 + 3 + 2 + 3


def test_measure_counts_file_bytes_not_characters(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("é" * 3, encoding="utf-8")
    budget = measure_context_budget(tmp_path)
    assert budget.sources[0].bytes == 6
    assert budget.sources[0].tokens == 2


def test_measure_ignores_a_skill_dir_without_skill_md(tmp_path: Path) -> None:
    (tmp_path / "skills" / "empty").mkdir(parents=True)
    (tmp_path / ".claude" / "skills").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    assert measure_context_budget(tmp_path).is_empty is True


def test_format_report_lists_rows_then_total() -> None:
    budget = ContextBudget(
        sources=(
            ContextSource(kind="directive", path="<prompt_rewrite directive>", bytes=8, tokens=2),
            ContextSource(kind="skill", path="skills/a/SKILL.md", bytes=400, tokens=100),
        ),
        total_bytes=408,
        total_tokens=102,
    )
    assert format_report(budget) == (
        "directive         8 B  ~2 tok  <prompt_rewrite directive>\n"
        "skill           400 B  ~100 tok  skills/a/SKILL.md\n"
        "TOTAL           408 B  ~102 tok  (tokens ≈ bytes/4)"
    )


def test_format_report_empty_budget_is_just_the_total() -> None:
    empty = ContextBudget(sources=(), total_bytes=0, total_tokens=0)
    assert format_report(empty) == "TOTAL             0 B  ~0 tok  (tokens ≈ bytes/4)"
