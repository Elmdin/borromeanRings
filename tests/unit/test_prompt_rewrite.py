"""Tests for the prompt-rewrite directive builder (docs/specs/SPEC-prompt-rewrite.md)."""

from meta_harness.prompt_rewrite import build_directive


def test_directive_includes_declared_context() -> None:
    directive = build_directive(
        {"account": "3MagicLabs/borromeanrings", "value_priorities": ["correctness", "security"]}
    )
    assert "REWRITE the user's request" in directive
    assert "operating context: 3MagicLabs/borromeanrings" in directive
    assert "value priorities (highest first): correctness, security" in directive


def test_directive_without_context_omits_optional_lines() -> None:
    """The optional lines are absent, asserted on the label the builder actually emits.

    These assertions previously named "account in effect", a phrase the builder no
    longer produces in either branch — so they passed whether the line was omitted
    or not. A negative assertion has to name the string the positive case emits, or
    it tests nothing.
    """
    directive = build_directive({})
    assert "REWRITE the user's request" in directive
    assert "operating context:" not in directive
    assert "value priorities" not in directive


def test_the_directive_keeps_every_obligation_however_it_is_worded() -> None:
    """Pin the obligations, not the prose (#135/ADR-0055).

    The directive is injected on every prompt, so it is a standing target for
    trimming. Wording may tighten; these five duties may not quietly disappear
    with it. Each is asserted by a token the SPEC's contract turns on rather than
    by a full sentence, so a rewrite that preserves meaning still passes.
    """
    directive = build_directive({"account": "acct", "value_priorities": ["correctness"]})
    assert "REWRITE" in directive  # rewrite before acting
    assert "no scope they did not ask for" in directive  # no scope creep
    assert "Reading this as:" in directive  # the reading is visible
    assert "Never pass your rewrite off as the user's words" in directive  # never impersonate

    # Confirm-first is asserted as the whole IMPERATIVE clause, not as the words
    # "irreversible" and "confirm" appearing somewhere. A review of this test showed
    # that the keyword form still passed when the duty was downgraded to a
    # suggestion ("you may want to confirm"), which is precisely the regression the
    # test exists to catch: a trim that keeps the vocabulary and drops the force.
    assert "STOP and confirm" in directive
    assert "irreversible (merge, publish, delete, deploy)" in directive
    for hedge in ("you may want to", "consider ", "it is a good idea", "try to"):
        assert hedge not in directive.lower(), f"an obligation was softened with {hedge!r}"


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
