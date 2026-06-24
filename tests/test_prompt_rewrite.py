"""Tests for the prompt-rewrite directive builder (docs/specs/SPEC-prompt-rewrite.md)."""

from meta_harness.prompt_rewrite import build_directive


def test_directive_includes_declared_context() -> None:
    directive = build_directive(
        {"account": "Elmdin/borromeanrings", "value_priorities": ["correctness", "security"]}
    )
    assert "preserve its intent" in directive
    assert "Elmdin/borromeanrings" in directive
    assert "correctness, security" in directive
    assert "confirm or edit" in directive  # propose, don't auto-apply


def test_directive_without_context_omits_optional_lines() -> None:
    directive = build_directive({})
    assert "preserve its intent" in directive
    assert "account in effect" not in directive
    assert "value priorities" not in directive
