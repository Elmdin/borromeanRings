"""Tests for git-identity enforcement logic (docs/specs/SPEC-git-identity.md)."""

from meta_harness.git_identity import (
    Identity,
    author_violations,
    command_override_violation,
    configured_violation,
    git_subcommand,
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


# --- per-command identity overrides (issue #54) ---------------------------------------
# The repo's *configured* identity being right does not mean the COMMIT will be right:
# git accepts an identity on the command line and in the environment, each of which
# overrides config for that invocation. Each of these is an evasion of the guard.

OVERRIDE_DECLARED = Identity(name="wimaan3", email="right@example.com")


def test_plain_commit_has_no_override() -> None:
    assert command_override_violation("git commit -m 'x'", OVERRIDE_DECLARED) is None


def test_author_flag_with_wrong_identity_is_a_violation() -> None:
    v = command_override_violation(
        'git commit --author="Wrong <bad@example.com>"', OVERRIDE_DECLARED
    )
    assert v is not None
    assert "bad@example.com" in v


def test_author_flag_space_separated_form() -> None:
    v = command_override_violation(
        'git commit --author "Wrong <bad@example.com>"', OVERRIDE_DECLARED
    )
    assert v is not None


def test_inline_config_email_override_is_a_violation() -> None:
    v = command_override_violation(
        "git -c user.email=bad@example.com commit -m x", OVERRIDE_DECLARED
    )
    assert v is not None
    assert "bad@example.com" in v


def test_inline_config_name_override_is_a_violation() -> None:
    assert (
        command_override_violation("git -c user.name=Wrong commit -m x", OVERRIDE_DECLARED)
        is not None
    )


def test_author_env_var_override_is_a_violation() -> None:
    v = command_override_violation(
        "GIT_AUTHOR_EMAIL=bad@example.com git commit -m x", OVERRIDE_DECLARED
    )
    assert v is not None


def test_committer_env_var_override_is_a_violation() -> None:
    v = command_override_violation(
        "GIT_COMMITTER_EMAIL=bad@example.com git commit -m x", OVERRIDE_DECLARED
    )
    assert v is not None


def test_override_matching_the_declared_identity_is_allowed() -> None:
    """Stating the correct identity explicitly is not an evasion."""
    ok = 'git commit --author="wimaan3 <right@example.com>"'
    assert command_override_violation(ok, OVERRIDE_DECLARED) is None
    assert (
        command_override_violation("git -c user.email=right@example.com commit", OVERRIDE_DECLARED)
        is None
    )


def test_unparseable_command_containing_an_override_is_refused() -> None:
    """An override we cannot parse must not be waved through.

    Failing open here would make the guard trivially evadable by mangling quoting.
    """
    v = command_override_violation("git commit --author='unbalanced <x@y.z>", OVERRIDE_DECLARED)
    assert v is not None


def test_unparseable_command_without_an_override_is_ignored() -> None:
    """Only identity overrides are this function's business."""
    assert command_override_violation("echo 'unbalanced", OVERRIDE_DECLARED) is None


def test_no_declared_identity_means_no_enforcement() -> None:
    unset = Identity(name="", email="")
    assert command_override_violation('git commit --author="A <a@b.c>"', unset) is None


def test_non_git_command_is_ignored() -> None:
    assert command_override_violation("echo --author=nonsense", OVERRIDE_DECLARED) is None


# --- subcommand detection: the evasion a substring match walks straight past -----------


def test_plain_invocation() -> None:
    assert git_subcommand("git commit -m x") == "commit"
    assert git_subcommand("git push origin main") == "push"


def test_global_options_between_git_and_the_subcommand() -> None:
    """This spelling contains no "git commit" substring at all."""
    assert git_subcommand("git -c user.email=bad@x.com commit -m x") == "commit"
    assert git_subcommand("git -C /some/path push") == "push"
    assert git_subcommand("git --git-dir=/tmp/x.git commit") == "commit"


def test_leading_environment_assignments_are_stepped_over() -> None:
    assert git_subcommand("GIT_AUTHOR_EMAIL=bad@x.com git commit -m x") == "commit"


def test_absolute_path_to_git_still_counts() -> None:
    assert git_subcommand("/usr/bin/git commit -m x") == "commit"


def test_non_git_and_unparseable_yield_nothing() -> None:
    assert git_subcommand("echo git commit") == ""
    assert git_subcommand("git commit --author='unbalanced") == ""


def test_unparseable_non_git_command_is_not_refused() -> None:
    """An unbalanced quote near an identity flag in a NON-git command is not our business."""
    assert command_override_violation("echo --author='oops", OVERRIDE_DECLARED) is None


def test_a_heredoc_merely_mentioning_git_is_not_a_commit() -> None:
    """Writing a file that talks about git must not be mistaken for committing."""
    text = "python3 script.py  # explains git -c user.email=someone@example.com commit"
    assert command_override_violation(text, OVERRIDE_DECLARED) is None


# --- remaining branches of the override parser ----------------------------------------


def test_git_with_only_global_options_has_no_subcommand() -> None:
    """`git -c k=v` with nothing after it invokes nothing."""
    assert git_subcommand("git -c user.email=a@b.c") == ""


def test_bare_email_author_value_is_compared_directly() -> None:
    """`--author` given a bare address (no `Name <...>` wrapper) is still checked."""
    assert (
        command_override_violation("git commit --author=bad@example.com", OVERRIDE_DECLARED)
        is not None
    )


def test_attached_inline_config_form_is_detected() -> None:
    """git also accepts the option and its value joined as one argv entry."""
    assert (
        command_override_violation(
            "git -cuser.email=bad@example.com commit -m x", OVERRIDE_DECLARED
        )
        is not None
    )
    assert (
        command_override_violation("git -cuser.name=Wrong commit -m x", OVERRIDE_DECLARED)
        is not None
    )


def test_wrong_display_name_in_author_is_reported() -> None:
    """A correct address with the wrong name is still the wrong identity."""
    v = command_override_violation(
        'git commit --author="Someone Else <right@example.com>"', OVERRIDE_DECLARED
    )
    assert v is not None
    assert "Someone Else" in v


def test_empty_override_value_is_ignored() -> None:
    """An option with no value asserts no identity, so there is nothing to violate."""
    assert command_override_violation("git commit --author=", OVERRIDE_DECLARED) is None
