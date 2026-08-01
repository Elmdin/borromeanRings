"""Tests for git-identity enforcement logic (docs/specs/SPEC-git-identity.md)."""

from meta_harness.git_identity import (
    Identity,
    author_violations,
    configured_violation,
    is_enforced,
)

DECLARED = Identity(name="wimaan3", email="imaansoltan@gmail.com")


def test_not_enforced_when_undeclared() -> None:
    empty = Identity(name="", email="")
    assert is_enforced(empty) is False
    assert configured_violation(Identity("someone", "x@y.z"), empty) is None
    assert author_violations([Identity("someone", "x@y.z")], empty) == []


def test_enforced_when_any_field_declared() -> None:
    assert is_enforced(DECLARED) is True
    assert is_enforced(Identity(name="", email="x@y.z")) is True
    assert is_enforced(Identity(name="x", email="")) is True


def test_configured_match_has_no_violation() -> None:
    assert configured_violation(DECLARED, DECLARED) is None


def test_configured_email_mismatch_is_violation() -> None:
    reason = configured_violation(Identity("wimaan3", "other@evil.com"), DECLARED)
    assert reason is not None
    assert "user.email" in reason
    assert "imaansoltan@gmail.com" in reason


def test_configured_unset_identity_is_violation() -> None:
    reason = configured_violation(Identity("", ""), DECLARED)
    assert reason is not None
    assert "(unset)" in reason


def test_only_declared_fields_are_checked() -> None:
    # Declare email only: any name is acceptable, wrong email is not.
    email_only = Identity(name="", email="imaansoltan@gmail.com")
    assert configured_violation(Identity("anyone", "imaansoltan@gmail.com"), email_only) is None
    assert configured_violation(Identity("anyone", "nope@x.com"), email_only) is not None


def test_author_violations_lists_only_offenders() -> None:
    authors = [
        Identity("wimaan3", "imaansoltan@gmail.com"),  # ok
        Identity("ghostwriter", "ghost@somewhere.com"),  # bad
        Identity("wimaan3", "imaansoltan@gmail.com"),  # ok
    ]
    bad = author_violations(authors, DECLARED)
    assert bad == ["ghostwriter <ghost@somewhere.com>"]


def test_author_violations_empty_when_all_match() -> None:
    authors = [Identity("wimaan3", "imaansoltan@gmail.com")] * 3
    assert author_violations(authors, DECLARED) == []
