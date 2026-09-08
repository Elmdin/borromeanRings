"""Unit tests for the single-project self-report (meta_harness.self_status).

Answers, from inside any session: *is borromeanRings governing THIS project, is
enforcement actually on, was the last verdict real or hollow?*
"""

from __future__ import annotations

from meta_harness.status_assess import (
    HOOK_EVENTS,
    HOOK_SCRIPTS,
    classify_enforcement,
    hollow_checks,
    render_self_status,
)
from meta_harness.verdict import Verdict

HOME = "/opt/borromeanrings"


def _hooks(events: list[str], command_prefix: str = HOME) -> dict[str, object]:
    """A settings.json 'hooks' block wiring ``events`` to borromeanRings's hook scripts."""
    return {
        "hooks": {
            event: [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"{command_prefix}/.claude/hooks/{HOOK_SCRIPTS[event]}",
                        }
                    ]
                }
            ]
            for event in events
        }
    }


# --- enforcement classification -------------------------------------------------------


def test_all_hooks_wired_is_automatic_enforcement() -> None:
    result = classify_enforcement(_hooks(list(HOOK_EVENTS)), HOME)
    assert result.mode == "auto"
    assert f"{len(HOOK_EVENTS)}/{len(HOOK_EVENTS)}" in result.detail


def test_no_settings_file_is_manual_only() -> None:
    result = classify_enforcement(None, HOME)
    assert result.mode == "manual"
    assert "manual" in result.detail.lower() or "no " in result.detail.lower()


def test_disabled_hooks_key_is_reported_as_disabled_not_absent() -> None:
    """The real field case: hooks renamed to _disabled_hooks_<date> — off, but recoverable."""
    settings = {"_disabled_hooks_2026-08-12": _hooks(list(HOOK_EVENTS))["hooks"]}
    result = classify_enforcement(settings, HOME)
    assert result.mode == "manual"
    assert "disabled" in result.detail.lower()
    assert "_disabled_hooks_2026-08-12" in result.detail


def test_partially_wired_hooks_are_flagged() -> None:
    result = classify_enforcement(_hooks(["Stop"]), HOME)
    assert result.mode == "partial"
    assert f"1/{len(HOOK_EVENTS)}" in result.detail


def test_non_borromeanrings_hooks_do_not_count_as_enforcement() -> None:
    """Someone else's hooks are not borromeanRings governing this project."""
    settings = {
        "hooks": {
            event: [{"hooks": [{"type": "command", "command": "/usr/bin/my-own-script.sh"}]}]
            for event in HOOK_EVENTS
        }
    }
    assert classify_enforcement(settings, HOME).mode == "manual"


def test_self_governing_repo_counts_as_enforced() -> None:
    """borromeanRings governs itself via ${CLAUDE_PROJECT_DIR}, not an absolute home.

    Detecting by path would report the harness's own repo — and any project using a
    variable — as unenforced, which is exactly backwards.
    """
    result = classify_enforcement(_hooks(list(HOOK_EVENTS), "${CLAUDE_PROJECT_DIR}"), HOME)
    assert result.mode == "auto"


def test_plugin_path_spelling_counts_as_enforced() -> None:
    """Hooks wired through the Claude Code plugin (ADR-0057) use the plugin's own variable.

    ``hooks/hooks.json`` spells every command as ``"${CLAUDE_PLUGIN_ROOT}"/.claude/hooks/x``
    (quoted, per the plugins reference). Classification matches on the script NAME, so
    the spelling — and the surrounding quotes — must not matter; a project governed
    through the plugin must read AUTO, not manual.
    """
    result = classify_enforcement(_hooks(list(HOOK_EVENTS), '"${CLAUDE_PLUGIN_ROOT}"'), HOME)
    assert result.mode == "auto"
    assert result.detail.startswith(f"{len(HOOK_EVENTS)}/{len(HOOK_EVENTS)} hooks wired")


def test_empty_hooks_object_is_manual() -> None:
    assert classify_enforcement({"hooks": {}}, HOME).mode == "manual"


def test_a_malformed_entry_is_skipped_not_treated_as_the_end_of_the_list() -> None:
    """One bad entry must not abandon the scan of the remaining entries.

    A `continue` that became a `break` would stop at the first malformed entry and report
    enforcement as OFF while all four hooks were in fact wired — telling someone their
    gate is unenforced when it is.
    """
    settings = {
        "hooks": {
            event: [
                "not-a-mapping",  # skipped: not a Mapping
                {"matcher": "Bash"},  # skipped: no inner "hooks" list
                {"hooks": [{"type": "command", "command": f"/h/.claude/hooks/{script}"}]},
            ]
            for event, script in HOOK_SCRIPTS.items()
        }
    }
    assert classify_enforcement(settings, HOME).mode == "auto"


def test_malformed_settings_never_raise() -> None:
    for bad in ({"hooks": "nope"}, {"hooks": {"Stop": "nope"}}, {"hooks": {"Stop": [1, 2]}}):
        assert classify_enforcement(bad, HOME).mode in {"auto", "manual", "partial"}


# --- hollow-check detection -----------------------------------------------------------


def test_hollow_checks_lists_only_noop_entries() -> None:
    v = Verdict(ok=True, checks=(("00_build", "noop"), ("20_lint", "pass"), ("x", "noop")))
    assert hollow_checks(v) == ("00_build", "x")


def test_hollow_checks_on_missing_verdict_is_empty() -> None:
    assert hollow_checks(None) == ()


# --- rendering ------------------------------------------------------------------------


def test_render_flags_a_hollow_green_prominently() -> None:
    v = Verdict(
        ok=True,
        checks=(("00_build", "noop"), ("30_typecheck", "noop"), ("20_lint", "pass")),
        run_id="r1",
        harness_version="v0.1.0",
    )
    text = render_self_status(
        project="/home/u/proj",
        governed=True,
        required=("00_build", "30_typecheck", "20_lint"),
        last_verdict=v,
        enforcement=classify_enforcement(None, HOME),
        harness_home=HOME,
    )
    assert "PASS" in text
    assert "2 of 3" in text  # two checks inspected nothing
    assert "00_build" in text and "30_typecheck" in text
    assert "v0.1.0" in text


def test_render_on_ungoverned_project_says_how_to_fix() -> None:
    text = render_self_status(
        project="/home/u/plain",
        governed=False,
        required=(),
        last_verdict=None,
        enforcement=classify_enforcement(None, HOME),
        harness_home=HOME,
    )
    assert "not governed" in text.lower()
    assert "init.sh" in text


def test_render_states_a_fact_about_the_record_not_a_claim_about_reality() -> None:
    """No hollow entries ⇒ report "0 recorded", never "all checks did real work".

    A verdict written before ``noop`` existed *could not* record hollowness, so inferring
    health from its absence would be exactly the over-claim this report exists to expose.
    """
    v = Verdict(ok=True, checks=(("20_lint", "pass"), ("40_test", "pass")), run_id="r")
    text = render_self_status(
        project="/p",
        governed=True,
        required=("20_lint", "40_test"),
        last_verdict=v,
        enforcement=classify_enforcement(_hooks(list(HOOK_EVENTS)), HOME),
        harness_home=HOME,
        installed_version="v0.1.0",
    )
    assert "0 of 2 checks recorded as inspecting nothing" in text
    assert "did real work" not in text  # never assert health the record cannot support
    assert "Installed:" in text and "v0.1.0" in text


def test_render_verdict_with_no_checks_claims_nothing_either_way() -> None:
    """An empty check list is neither hollow nor 'all real' — say neither."""
    text = render_self_status(
        project="/p",
        governed=True,
        required=(),
        last_verdict=Verdict(ok=True, checks=()),
        enforcement=classify_enforcement(None, HOME),
        harness_home=HOME,
    )
    assert "did real work" not in text
    assert "inspected NOTHING" not in text


def test_hook_entry_without_a_hooks_list_is_skipped() -> None:
    """A malformed entry (no inner 'hooks' list) must not count as wired."""
    settings = {"hooks": {event: [{"matcher": "Bash"}] for event in HOOK_EVENTS}}
    assert classify_enforcement(settings, HOME).mode == "manual"


def test_render_never_gated_project_does_not_claim_a_verdict() -> None:
    text = render_self_status(
        project="/p",
        governed=True,
        required=("00_build",),
        last_verdict=None,
        enforcement=classify_enforcement(None, HOME),
        harness_home=HOME,
    )
    assert "never" in text.lower()
    assert "PASS" not in text
