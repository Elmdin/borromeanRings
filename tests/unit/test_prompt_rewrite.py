"""Tests for the prompt-rewrite directive builder (docs/specs/SPEC-prompt-rewrite.md)."""

from meta_harness.prompt_rewrite import build_directive


def test_directive_includes_declared_context() -> None:
    directive = build_directive(
        {"account": "Elmdin/borromeanrings", "value_priorities": ["correctness", "security"]}
    )
    assert "preserve its intent" in directive
    assert "Elmdin/borromeanrings" in directive
    assert "correctness, security" in directive


def test_directive_without_context_omits_optional_lines() -> None:
    directive = build_directive({})
    assert "preserve its intent" in directive
    assert "account in effect" not in directive
    assert "value priorities" not in directive


def test_directive_contract_is_cheap_and_visible() -> None:
    """The observable contract is a one-line reading, not a confirm ceremony.

    The original directive demanded show-the-rewrite-and-ask-to-confirm on
    every non-trivial prompt; in real sessions agents rationalized it away and
    the feature became invisible (issue #81). The contract is now cheap enough
    to survive: open the reply with a 'Reading this as:' line, and reserve
    confirm-first for irreversible or scope-changing readings.
    """
    directive = build_directive({})
    assert "Reading this as:" in directive
    assert "irreversible" in directive
    assert "confirm" in directive  # still confirm-first where it matters
    # the heavyweight ceremony is gone:
    assert "PROPOSE" not in directive
