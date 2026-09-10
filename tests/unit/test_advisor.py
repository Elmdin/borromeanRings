"""Unit tests for the approach advisor (meta_harness.advisor; SPEC-approach-advisor.md).

Exact-value tests: every rule is shown to fire on facts built to trip it and to stay
silent on facts built not to; the order is the one fixed order (questions, then
approaches, each in catalog order); the no-facts case says "no advice" rather than
inventing some. The catalog-integrity test pins that every rule's ``source`` names a
check, SPEC or ADR that exists on this base.
"""

from __future__ import annotations

import json
import re

from meta_harness.advisor import (
    APPROACH,
    CATALOG,
    NO_FACTS_NOTE,
    QUESTION,
    RATCHETS,
    Advice,
    Facts,
    FeatureGap,
    Line,
    Rule,
    advise,
    gather_facts,
    render,
    to_json,
)
from meta_harness.verdict import Verdict

HEALTH = FeatureGap(
    "health_endpoint_declared", "a health/readiness endpoint route is declared", "O6"
)
USAGE = FeatureGap("usage_documented", "usage is documented in the README", "Nielsen #10")


def _facts(**overrides: object) -> Facts:
    base: dict[str, object] = {
        "project": "/tmp/proj",
        "gated": True,
        "archetypes": (),
        "failing": (),
        "noop": (),
        "ratchets_without_baseline": (),
        "recommended": (),
        "features_absent": (),
        "required": (),
        "heavy": (),
        "live": (),
        "adr_prefixes": (),
        "branch": "",
        "changed": (),
        "changed_src": (),
        "changed_tests": False,
        "changed_adr": False,
        "changed_changelog": False,
        "enforcement": "auto",
        "stakes": "",
        "reviewer": "",
        "unreadable": (),
    }
    base.update(overrides)
    return Facts(**base)  # type: ignore[arg-type]


def _ids(lines: tuple[Line, ...]) -> list[str]:
    return [line.rule for line in lines]


def _rule(rule_id: str) -> Rule:
    return next(rule for rule in CATALOG if rule.id == rule_id)


#: A project that has adopted every check the catalog cites, with each opt-in rule on.
LIVE = ("08_branch", "13_adr", "40_test", "11_changelog", "21_archetype")


# --- catalog integrity ---------------------------------------------------------------------


def test_catalog_has_at_least_twelve_unique_well_formed_rules() -> None:
    assert len(CATALOG) >= 12
    ids = [rule.id for rule in CATALOG]
    assert len(set(ids)) == len(ids)
    for rule in CATALOG:
        assert rule.kind in (QUESTION, APPROACH), rule.id
        assert rule.text.strip() == rule.text and rule.text, rule.id
        assert callable(rule.when), rule.id


def test_every_rule_source_is_a_well_formed_citation() -> None:
    """Shape only. That each citation NAMES SOMETHING THAT EXISTS is the integrity test in
    tests/integration/test_advise_cli.py: it reads the repo by path, and mutmut's sandbox
    copies only src/ and tests/, so a path-reading test belongs in the ignored suite."""
    for rule in CATALOG:
        src = rule.source
        assert re.fullmatch(r"SPEC-[a-z0-9-]+\.md|ADR-\d{4}|\d{2}_[a-z][a-z0-9_]*", src), (
            f"{rule.id}: {src}"
        )


def test_ratchet_vocabulary_matches_the_checks_that_ratchet() -> None:
    assert RATCHETS == ("32_complexity", "33_coupling", "45_docstrings", "40_test", "60_mutation")


# --- gather_facts ------------------------------------------------------------------------------


VERDICT = Verdict(
    ok=False,
    checks=(
        ("00_build", "pass"),
        ("14_container", "noop"),
        ("21_archetype", "fail"),
        ("33_coupling", "error"),
        ("99_not_required", "fail"),
    ),
    run_id="r1",
)


def test_gather_facts_classifies_failing_noop_ratchets_recommended_and_diff() -> None:
    facts = gather_facts(
        project="/tmp/proj",
        required=("00_build", "14_container", "21_archetype", "33_coupling", "70_pip_audit"),
        verdict=VERDICT,
        archetypes=("web-api",),
        features_absent=(HEALTH,),
        has_changelog=False,
        baseline_files_present=(),
        heavy=("70_pip_audit",),
        branch="feat/x",
        changed=("src/pkg/a.py", "src_generated/b.py", "docs/adr/0072-x.md", "README.md"),
        adr_prefixes=("feat/",),
        enforcement="manual",
        stakes="high",
        reviewer="",
        unreadable=(),
    )
    assert facts == Facts(
        project="/tmp/proj",
        gated=True,
        archetypes=("web-api",),
        failing=(("21_archetype", "fail"), ("33_coupling", "error")),
        noop=("14_container",),
        ratchets_without_baseline=("33_coupling",),
        recommended=(
            "12_secrets",
            "11_changelog",
            "32_complexity",
            "45_docstrings",
            "01_source_coherence",
        ),
        features_absent=(HEALTH,),
        required=("00_build", "14_container", "21_archetype", "33_coupling", "70_pip_audit"),
        heavy=("70_pip_audit",),
        live=("00_build", "14_container", "21_archetype", "33_coupling", "70_pip_audit"),
        adr_prefixes=("feat/",),
        branch="feat/x",
        changed=("src/pkg/a.py", "src_generated/b.py", "docs/adr/0072-x.md", "README.md"),
        changed_src=("src/pkg/a.py",),
        changed_tests=False,
        changed_adr=True,
        changed_changelog=False,
        enforcement="manual",
        stakes="high",
        reviewer="",
        unreadable=(),
    )


def test_gather_facts_never_gated_is_unknown_not_lacking() -> None:
    facts = gather_facts(
        project="p",
        required=("00_build", "33_coupling"),
        verdict=None,
        archetypes=(),
        features_absent=(),
        has_changelog=True,
        baseline_files_present=(".borromeanrings-coupling-baseline",),
        changed=("tests/unit/test_a.py", "CHANGELOG.md", "src"),
        src_dir="src",
        tests_dir="tests",
    )
    assert facts.gated is False
    assert facts.failing == () and facts.noop == ()
    assert facts.ratchets_without_baseline == ()
    assert facts.changed_src == ("src",)  # the directory itself counts; "src_x" would not
    assert facts.changed_tests is True and facts.changed_changelog is True
    assert facts.changed_adr is False
    assert facts.recommended == (
        "12_secrets",
        "11_changelog",
        "32_complexity",
        "45_docstrings",
        "01_source_coherence",
        "21_archetype",
    )
    assert facts.branch == "" and facts.enforcement == "" and facts.unreadable == ()


def test_gather_facts_unreadable_config_derives_nothing_from_it() -> None:
    facts = gather_facts(
        project="p",
        required=(),
        verdict=VERDICT,
        archetypes=(),
        features_absent=(),
        has_changelog=False,
        baseline_files_present=(),
        unreadable=("config",),
    )
    assert facts.recommended == ()
    assert facts.failing == () and facts.noop == ()  # nothing required ⇒ nothing lacking
    assert facts.unreadable == ("config",)


def test_gather_facts_honours_custom_src_and_tests_dirs() -> None:
    facts = gather_facts(
        project="p",
        required=(),
        verdict=None,
        archetypes=(),
        features_absent=(),
        has_changelog=False,
        baseline_files_present=(),
        changed=("lib/a.py", "spec/test_a.py", "docs/adr/0001-x.md"),
        src_dir="lib",
        tests_dir="spec",
    )
    assert facts.changed_src == ("lib/a.py",)
    assert facts.changed_tests is True and facts.changed_adr is True


# --- rules: each fires, and stays silent ----------------------------------------------------


def test_no_facts_yields_the_note_and_nothing_else() -> None:
    advice = advise(_facts(gated=False, enforcement=""))
    assert advice == Advice(
        facts=_facts(gated=False, enforcement=""), questions=(), approaches=(), note=NO_FACTS_NOTE
    )
    assert NO_FACTS_NOTE == "no advice: never gated, no archetypes"


def test_never_gated_with_archetype_asks_and_points_at_the_playbook() -> None:
    advice = advise(_facts(gated=False, archetypes=("cli",), enforcement=""))
    assert advice.note == ""
    assert _ids(advice.questions) == ["q_never_gated"]
    assert _ids(advice.approaches) == ["a_playbook"]
    assert advice.questions[0] == Line(
        "q_never_gated",
        "this project has never been gated — run verify.sh before starting, or is the gate"
        " deliberately off?",
        "SPEC-self-status.md",
    )
    assert advice.approaches[0] == Line(
        "a_playbook",
        "archetype(s) cli declared ⇒ read the catalog playbook for each"
        " (meta_harness.archetypes.CATALOG[name].playbook) before designing the change",
        "ADR-0062",
    )


def test_declared_stakes_alone_are_facts_enough_to_advise() -> None:
    """A charter with stakes is something the record says, so it is never "no advice"."""
    advice = advise(_facts(gated=False, enforcement="", stakes="high", heavy=("60_mutation",)))
    assert advice.note == ""
    assert _ids(advice.questions) == ["q_reviewer"]
    assert _ids(advice.approaches) == ["a_heavy_lane_high_stakes"]


def test_never_gated_with_only_a_diff_is_not_the_no_facts_case() -> None:
    facts = _facts(gated=False, enforcement="", changed=("x",), changed_src=("x",), live=LIVE)
    advice = advise(facts)
    assert advice.note == ""
    assert _ids(advice.questions) == []
    assert _ids(advice.approaches) == ["a_test_first", "a_changelog_with_change"]


def test_unreadable_inputs_become_a_question_not_a_guess() -> None:
    advice = advise(_facts(gated=False, enforcement="", unreadable=("config", "verdict")))
    assert _ids(advice.questions) == ["q_unreadable"]
    assert advice.questions[0].text == (
        "config, verdict could not be read — fix the record (borromeanrings.toml,"
        " .meta-harness/last_verdict.json) before building on it?"
    )
    assert advice.questions[0].source == "SPEC-swe-state.md"
    assert advice.approaches == ()


def test_unreadable_question_names_what_actually_broke_not_a_fixed_pair_of_files() -> None:
    def text(*buckets: str) -> str:
        return advise(_facts(gated=False, enforcement="", unreadable=buckets)).questions[0].text

    assert text("archetypes") == (
        "archetypes could not be read — fix the record (the working tree the archetype"
        " evaluation walked) before building on it?"
    )
    assert text("charter") == (
        "charter could not be read — fix the record (borromeanrings.toml [charter]) before"
        " building on it?"
    )
    assert text("verdict") == (
        "verdict could not be read — fix the record (.meta-harness/last_verdict.json) before"
        " building on it?"
    )
    # an unknown bucket names itself rather than being dropped or mislabelled
    assert text("something_new").startswith(
        "something_new could not be read — fix the record (something_new)"
    )


def test_enforcement_off_asks_before_rewiring() -> None:
    for mode in ("manual", "partial"):
        advice = advise(_facts(enforcement=mode))
        assert _ids(advice.questions) == ["q_enforcement_off", "q_no_archetype"], mode
        assert advice.questions[0].text == (
            f"enforcement is {mode.upper()} here — the gate runs only when invoked; should the"
            " hooks be wired before you begin (the user's decision, not yours)?"
        )
    assert _ids(advise(_facts(enforcement="auto")).questions) == ["q_no_archetype"]
    assert _ids(
        advise(_facts(gated=False, archetypes=("cli",), enforcement="manual")).questions
    ) == ["q_never_gated"]


def test_no_archetype_on_a_gated_project_asks_what_kind_of_app() -> None:
    advice = advise(_facts())
    assert advice.questions == (
        Line(
            "q_no_archetype",
            "no archetype is declared — what kind of application is this (cli, library,"
            " web-api, web-app, ml, embedded, data-pipeline)? [project].archetypes is the"
            " declaration 21_archetype reads; while it is empty that dimension is off",
            "21_archetype",
        ),
    )
    assert advice.approaches == ()
    assert _ids(advise(_facts(archetypes=("library",))).questions) == []


def test_a11y_hollow_on_a_web_app_asks_about_html() -> None:
    advice = advise(_facts(archetypes=("web-app",), noop=("15_a11y",)))
    assert _ids(advice.questions) == ["q_a11y_hollow_web_app"]
    assert advice.questions[0] == Line(
        "q_a11y_hollow_web_app",
        "the last verdict is hollow on 15_a11y for a web-app — is there really no HTML"
        " here, or does [a11y] / the tree not match reality?",
        "15_a11y",
    )
    # the same noop on a non-web-app is the general hollow question instead
    other = advise(_facts(archetypes=("cli",), noop=("15_a11y",)))
    assert _ids(other.questions) == ["q_hollow_checks"]
    assert other.questions[0].text == (
        "15_a11y inspected NOTHING last run — is there truly nothing to inspect, or should"
        " each be pointed at something (or dropped from [checks].required)?"
    )
    assert other.questions[0].source == "ADR-0049"


def test_hollow_checks_lists_only_the_ones_the_a11y_rule_did_not_take() -> None:
    advice = advise(_facts(archetypes=("web-app",), noop=("15_a11y", "14_container")))
    assert _ids(advice.questions) == ["q_a11y_hollow_web_app", "q_hollow_checks"]
    assert advice.questions[1].text.startswith("14_container inspected NOTHING last run")
    assert _ids(advise(_facts(archetypes=("web-app",))).questions) == []


def test_reviewer_asked_only_when_stakes_are_declared_and_nobody_is_named() -> None:
    advice = advise(_facts(archetypes=("cli",), stakes="high"))
    assert _ids(advice.questions) == ["q_reviewer"]
    assert advice.questions[0] == Line(
        "q_reviewer",
        "stakes are high and no reviewer is named — who reviews and merges this"
        " (merge.sh is explicit and human)?",
        "ADR-0007",
    )
    assert _ids(advise(_facts(archetypes=("cli",), stakes="high", reviewer="ana")).questions) == []
    assert _ids(advise(_facts(archetypes=("cli",), reviewer="")).questions) == []


def test_branch_question_fires_off_a_work_branch_with_changes() -> None:
    advice = advise(
        _facts(archetypes=("cli",), branch="main", changed=("README.md",), live=("08_branch",))
    )
    assert _ids(advice.questions) == ["q_branch"]
    assert advice.questions[0] == Line(
        "q_branch",
        "you are on 'main' with changes in the tree — should this work be on a feat/ or"
        " fix/ branch (08_branch fails closed on protected branches)?",
        "08_branch",
    )
    for branch in ("feat/x", "fix/y", "docs/z", "test/t", "chore/c", "refactor/r", "perf/p"):
        assert _ids(
            advise(_facts(branch=branch, changed=("a",), live=("08_branch",))).questions
        ) == ["q_no_archetype"]
    for branch in ("ci/c", "hotfix/h", ""):
        assert _ids(
            advise(_facts(branch=branch, changed=("a",), live=("08_branch",))).questions
        ) == ["q_no_archetype"]
    assert _ids(advise(_facts(branch="dev", changed=(), live=("08_branch",))).questions) == [
        "q_no_archetype"
    ]
    # 08_branch not adopted here (or its patterns undeclared) ⇒ the advisor does not claim
    # a check will fail; it says nothing about the branch at all.
    assert _ids(advise(_facts(branch="main", changed=("a",))).questions) == ["q_no_archetype"]


def test_failing_ratchet_says_fix_the_design_never_the_baseline() -> None:
    advice = advise(
        _facts(archetypes=("cli",), failing=(("33_coupling", "fail"), ("40_test", "error")))
    )
    assert _ids(advice.approaches) == ["a_failing_ratchet", "a_playbook"]
    assert advice.approaches[0] == Line(
        "a_failing_ratchet",
        "a ratchet is failing (33_coupling (fail), 40_test (error)) ⇒ fix the design, never"
        " the baseline: split the module, reach siblings through one seam, test the branch",
        "ADR-0041",
    )


def test_failing_non_ratchet_says_fix_the_finding_first() -> None:
    advice = advise(
        _facts(archetypes=("cli",), failing=(("21_archetype", "fail"), ("33_coupling", "fail")))
    )
    assert _ids(advice.approaches) == ["a_failing_ratchet", "a_failing_gate", "a_playbook"]
    assert advice.approaches[1] == Line(
        "a_failing_gate",
        "the last verdict fails on 21_archetype (fail) ⇒ the gate is fail-closed: fix those"
        " findings before adding anything new",
        "ADR-0049",
    )
    assert _ids(advise(_facts(archetypes=("cli",))).approaches) == ["a_playbook"]


def test_ratchets_without_a_baseline_are_seeded_from_current_state() -> None:
    advice = advise(_facts(ratchets_without_baseline=("32_complexity", "45_docstrings")))
    assert _ids(advice.approaches) == ["a_ratchet_baseline"]
    assert advice.approaches[0] == Line(
        "a_ratchet_baseline",
        "ratchet(s) 32_complexity, 45_docstrings have no baseline ⇒ seed it from current state"
        " (adopt.sh) so the line holds; never pick a target",
        "ADR-0041",
    )


def test_feat_branch_touching_src_without_an_adr_says_spec_and_adr_first() -> None:
    facts = _facts(
        branch="feat/x",
        changed=("src/a.py",),
        changed_src=("src/a.py",),
        live=LIVE,
        adr_prefixes=("feat/",),
    )
    advice = advise(facts)
    assert _ids(advice.approaches) == [
        "a_spec_and_adr_first",
        "a_test_first",
        "a_changelog_with_change",
    ]
    assert advice.approaches[0] == Line(
        "a_spec_and_adr_first",
        "new surface on 'feat/x' touches src/a.py and no docs/adr/ file ⇒ decide first, on the"
        " record: a SPEC under docs/specs and an ADR under docs/adr before the code (13_adr"
        " fails closed without one)",
        "13_adr",
    )
    silent = (
        _facts(
            branch="fix/x",
            changed=("src/a.py",),
            changed_src=("src/a.py",),
            live=LIVE,
            adr_prefixes=("feat/",),
        ),
        _facts(
            branch="feat/x",
            changed=("src/a.py",),
            changed_src=("src/a.py",),
            changed_adr=True,
            live=LIVE,
            adr_prefixes=("feat/",),
        ),
        _facts(branch="feat/x", changed=("docs/a.md",), live=LIVE, adr_prefixes=("feat/",)),
        # 13_adr not adopted here: no claim that it fails closed
        _facts(
            branch="feat/x",
            changed=("src/a.py",),
            changed_src=("src/a.py",),
            adr_prefixes=("feat/",),
        ),
        # no trigger prefix declared ⇒ the rule has nothing to key on
        _facts(branch="feat/x", changed=("src/a.py",), changed_src=("src/a.py",), live=LIVE),
    )
    for f in silent:
        assert "a_spec_and_adr_first" not in _ids(advise(f).approaches)


def test_the_adr_trigger_prefix_is_the_declared_one_not_a_hardcoded_feat() -> None:
    facts = _facts(
        branch="story/x",
        changed=("src/a.py",),
        changed_src=("src/a.py",),
        live=LIVE,
        adr_prefixes=("story/",),
    )
    assert "a_spec_and_adr_first" in _ids(advise(facts).approaches)


def test_src_change_without_tests_says_failing_test_first() -> None:
    facts = _facts(
        changed=("src/a.py",), changed_src=("src/a.py",), changed_changelog=True, live=LIVE
    )
    advice = advise(facts)
    assert _ids(advice.approaches) == ["a_test_first"]
    assert advice.approaches[0] == Line(
        "a_test_first",
        "src/a.py changed with no test change ⇒ write the failing test first and show it fail"
        " (40_test ratchets coverage; a test that passes regardless is worse than none)",
        "40_test",
    )
    with_tests = _facts(
        changed_src=("src/a.py",), changed_tests=True, changed_changelog=True, live=LIVE
    )
    assert _ids(advise(with_tests).approaches) == []
    # 40_test not adopted here ⇒ no claim about what it ratchets
    not_adopted = _facts(changed=("src/a.py",), changed_src=("src/a.py",), changed_changelog=True)
    assert _ids(advise(not_adopted).approaches) == []


def test_src_change_without_changelog_says_write_the_entry_with_the_change() -> None:
    facts = _facts(changed=("src/a.py",), changed_src=("src/a.py",), changed_tests=True, live=LIVE)
    advice = advise(facts)
    assert _ids(advice.approaches) == ["a_changelog_with_change"]
    assert advice.approaches[0] == Line(
        "a_changelog_with_change",
        "src/a.py changed and CHANGELOG.md did not ⇒ write the [Unreleased] entry with the"
        " change, not at release time (11_changelog requires it on a source change)",
        "11_changelog",
    )
    # adopted but the entry-on-source-change rule is off ⇒ live excludes it ⇒ silent
    off = _facts(changed=("src/a.py",), changed_src=("src/a.py",), changed_tests=True)
    assert _ids(advise(off).approaches) == []


def test_web_api_without_a_health_route_adds_it_before_the_feature() -> None:
    advice = advise(_facts(archetypes=("web-api",), features_absent=(HEALTH,), live=LIVE))
    assert _ids(advice.approaches) == ["a_web_api_health", "a_playbook"]
    assert advice.approaches[0] == Line(
        "a_web_api_health",
        "archetype web-api with no health route ⇒ add /livez and /readyz before the feature"
        " (21_archetype fails closed on health_endpoint_declared)",
        "SPEC-archetypes.md",
    )
    # the same feature absent on a non-web-api project is the general rule instead
    other = advise(_facts(archetypes=("cli",), features_absent=(HEALTH,), live=LIVE))
    assert _ids(other.approaches) == ["a_archetype_features", "a_playbook"]


def test_other_absent_features_are_listed_with_their_why() -> None:
    advice = advise(
        _facts(archetypes=("web-api", "cli"), features_absent=(HEALTH, USAGE), live=LIVE)
    )
    assert _ids(advice.approaches) == ["a_web_api_health", "a_archetype_features", "a_playbook"]
    assert advice.approaches[1] == Line(
        "a_archetype_features",
        "archetype(s) web-api, cli lack required feature(s) usage_documented — usage is"
        " documented in the README (Nielsen #10) ⇒ add them before the feature; 21_archetype"
        " fails closed until they exist",
        "21_archetype",
    )
    only_health = advise(_facts(archetypes=("web-api",), features_absent=(HEALTH,), live=LIVE))
    assert "a_archetype_features" not in _ids(only_health.approaches)


def test_recommended_not_adopted_points_at_adopt_sh() -> None:
    advice = advise(_facts(recommended=("12_secrets", "11_changelog")))
    assert _ids(advice.approaches) == ["a_recommended"]
    assert advice.approaches[0] == Line(
        "a_recommended",
        "RECOMMENDED checks 12_secrets, 11_changelog are not required here ⇒ adopt.sh adds them"
        " and seeds their baselines; propose it, do not apply it silently",
        "ADR-0041",
    )


def test_high_stakes_prefers_the_heavy_lane() -> None:
    heavy = ("60_mutation", "74_secret_history")
    for stakes in ("high", "critical", "medium"):
        advice = advise(_facts(archetypes=("cli",), stakes=stakes, reviewer="ana", heavy=heavy))
        assert _ids(advice.approaches) == ["a_playbook", "a_heavy_lane_high_stakes"], stakes
        assert advice.approaches[1] == Line(
            "a_heavy_lane_high_stakes",
            f"stakes are {stakes} ⇒ run the heavy lane (verify.sh --heavy: 60_mutation,"
            " 74_secret_history) before the PR, not just the fast gate",
            "ADR-0033",
        )
    for stakes in ("low", "LOW", ""):
        assert "a_heavy_lane_high_stakes" not in _ids(
            advise(
                _facts(archetypes=("cli",), stakes=stakes, reviewer="ana", heavy=heavy)
            ).approaches
        )
    # no heavy lane declared ⇒ `verify.sh --heavy` would add nothing, so nothing is promised
    assert "a_heavy_lane_high_stakes" not in _ids(
        advise(_facts(archetypes=("cli",), stakes="high", reviewer="ana")).approaches
    )


def test_order_is_questions_then_approaches_each_in_catalog_order() -> None:
    facts = _facts(
        archetypes=("web-app",),
        failing=(("21_archetype", "fail"), ("32_complexity", "fail")),
        noop=("15_a11y", "14_container"),
        ratchets_without_baseline=("45_docstrings",),
        recommended=("12_secrets",),
        features_absent=(USAGE,),
        branch="main",
        changed=("src/a.py",),
        changed_src=("src/a.py",),
        live=LIVE,
        heavy=("60_mutation",),
        adr_prefixes=("feat/",),
        enforcement="partial",
        stakes="high",
        unreadable=("archetypes",),
    )
    advice = advise(facts)
    assert _ids(advice.questions) == [
        "q_unreadable",
        "q_enforcement_off",
        "q_a11y_hollow_web_app",
        "q_hollow_checks",
        "q_reviewer",
        "q_branch",
    ]
    assert _ids(advice.approaches) == [
        "a_failing_ratchet",
        "a_failing_gate",
        "a_ratchet_baseline",
        "a_test_first",
        "a_changelog_with_change",
        "a_archetype_features",
        "a_playbook",
        "a_recommended",
        "a_heavy_lane_high_stakes",
    ]
    catalog_ids = [rule.id for rule in CATALOG]
    fired = _ids(advice.questions) + _ids(advice.approaches)
    assert fired == [rule_id for rule_id in catalog_ids if rule_id in fired]
    assert [r.kind for r in CATALOG] == [QUESTION] * 8 + [APPROACH] * 11


def test_every_rule_fires_somewhere() -> None:
    facts = (
        _facts(gated=False, archetypes=("cli",), enforcement=""),
        _facts(unreadable=("config",)),
        _facts(
            archetypes=("web-app", "web-api"),
            failing=(("21_archetype", "fail"), ("32_complexity", "fail")),
            noop=("15_a11y", "14_container"),
            ratchets_without_baseline=("45_docstrings",),
            recommended=("12_secrets",),
            features_absent=(HEALTH, USAGE),
            branch="main",
            changed=("src/a.py",),
            changed_src=("src/a.py",),
            live=LIVE,
            heavy=("60_mutation",),
            enforcement="manual",
            stakes="high",
        ),
        _facts(
            branch="feat/x",
            changed=("src/a.py",),
            changed_src=("src/a.py",),
            live=LIVE,
            adr_prefixes=("feat/",),
        ),
    )
    fired = {line.rule for f in facts for line in advise(f).questions + advise(f).approaches}
    assert fired == {rule.id for rule in CATALOG}


# --- rendering -----------------------------------------------------------------------------


def test_render_pins_the_full_layout() -> None:
    facts = _facts(
        project="/home/u/proj/",
        archetypes=("web-api",),
        failing=(("21_archetype", "fail"),),
        noop=("14_container",),
        features_absent=(HEALTH,),
        live=LIVE,
        adr_prefixes=("feat/",),
        branch="feat/x",
        changed=("src/a.py", "tests/unit/test_a.py", "CHANGELOG.md"),
        changed_src=("src/a.py",),
        changed_tests=True,
        changed_changelog=True,
        enforcement="manual",
    )
    assert render(advise(facts)) == (
        "borromeanRings — approach advice for proj   (advisory; never a gate)\n"
        "\n"
        "Questions to ask before proceeding\n"
        "  1. enforcement is MANUAL here — the gate runs only when invoked; should the hooks"
        " be wired before you begin (the user's decision, not yours)?  [SPEC-self-status.md]\n"
        "  2. 14_container inspected NOTHING last run — is there truly nothing to inspect, or"
        " should each be pointed at something (or dropped from [checks].required)?"
        "  [ADR-0049]\n"
        "\n"
        "Approaches that fit this change\n"
        "  1. the last verdict fails on 21_archetype (fail) ⇒ the gate is fail-closed: fix"
        " those findings before adding anything new  [ADR-0049]\n"
        "  2. new surface on 'feat/x' touches src/a.py and no docs/adr/ file ⇒ decide first,"
        " on the record: a SPEC under docs/specs and an ADR under docs/adr before the code"
        " (13_adr fails closed without one)  [13_adr]\n"
        "  3. archetype web-api with no health route ⇒ add /livez and /readyz before the"
        " feature (21_archetype fails closed on health_endpoint_declared)"
        "  [SPEC-archetypes.md]\n"
        "  4. archetype(s) web-api declared ⇒ read the catalog playbook for each"
        " (meta_harness.archetypes.CATALOG[name].playbook) before designing the change"
        "  [ADR-0062]\n"
        "\n"
        "Facts: gated=yes · archetypes: web-api · branch: feat/x · enforcement: manual ·"
        " failing: 21_archetype (fail) · noop: 14_container · changed: 3 path(s) ·"
        " stakes: (no charter)\n"
        "Order: fixed — questions, then approaches, each in catalog order; no score,"
        " no ranking\n"
    )


def test_render_empty_sections_say_none_and_facts_say_unknown() -> None:
    facts = _facts(archetypes=("library",), enforcement="", stakes="low", reviewer="r")
    assert render(advise(facts)) == (
        "borromeanRings — approach advice for proj   (advisory; never a gate)\n"
        "\n"
        "Questions to ask before proceeding\n"
        "  (none)\n"
        "\n"
        "Approaches that fit this change\n"
        "  1. archetype(s) library declared ⇒ read the catalog playbook for each"
        " (meta_harness.archetypes.CATALOG[name].playbook) before designing the change"
        "  [ADR-0062]\n"
        "\n"
        "Facts: gated=yes · archetypes: library · branch: none · enforcement: unknown ·"
        " failing: none · noop: none · changed: 0 path(s) · stakes: low\n"
        "Order: fixed — questions, then approaches, each in catalog order; no score,"
        " no ranking\n"
    )


def test_render_no_facts_prints_the_note_instead_of_sections() -> None:
    assert render(advise(_facts(gated=False, enforcement=""))) == (
        "borromeanRings — approach advice for proj   (advisory; never a gate)\n"
        "\n"
        "  no advice: never gated, no archetypes\n"
        "\n"
        "Facts: gated=no · archetypes: none · branch: none · enforcement: unknown ·"
        " failing: none · noop: none · changed: 0 path(s) · stakes: (no charter)\n"
        "Order: fixed — questions, then approaches, each in catalog order; no score,"
        " no ranking\n"
    )


def test_to_json_is_asdict_with_lists() -> None:
    advice = advise(_facts(archetypes=("cli",), noop=("14_container",)))
    data = json.loads(to_json(advice))
    assert data["note"] == ""
    assert data["facts"]["archetypes"] == ["cli"]
    assert data["questions"] == [
        {
            "rule": "q_hollow_checks",
            "text": (
                "14_container inspected NOTHING last run — is there truly nothing to inspect,"
                " or should each be pointed at something (or dropped from [checks].required)?"
            ),
            "source": "ADR-0049",
        }
    ]
    assert [a["rule"] for a in data["approaches"]] == ["a_playbook"]
    assert to_json(advice).endswith("\n")


def test_rule_lookup_helper_finds_catalog_entries() -> None:
    assert _rule("a_playbook").kind == APPROACH
    assert _rule("q_branch").kind == QUESTION


def test_feature_gap_without_a_why_renders_without_empty_parentheses() -> None:
    gap = FeatureGap("watchdog_configured", "a watchdog is configured", "")
    advice = advise(_facts(archetypes=("embedded",), features_absent=(gap,), live=LIVE))
    assert advice.approaches[0].text == (
        "archetype(s) embedded lack required feature(s) watchdog_configured — a watchdog is"
        " configured ⇒ add them before the feature; 21_archetype fails closed until they exist"
    )


def test_live_excludes_checks_whose_own_opt_in_rule_is_off() -> None:
    def live(**flags: bool) -> tuple[str, ...]:
        return gather_facts(
            project="p",
            required=("08_branch", "11_changelog", "13_adr", "40_test"),
            verdict=None,
            archetypes=(),
            features_absent=(),
            has_changelog=True,
            baseline_files_present=(),
            **flags,  # type: ignore[arg-type]
        ).live

    assert live() == ("13_adr", "40_test")
    assert live(branch_patterns_declared=True) == ("08_branch", "13_adr", "40_test")
    assert live(changelog_entry_on_src=True) == ("11_changelog", "13_adr", "40_test")
    assert live(branch_patterns_declared=True, changelog_entry_on_src=True) == (
        "08_branch",
        "11_changelog",
        "13_adr",
        "40_test",
    )
    # a check that is not required is never live, however its sub-rule is set
    assert "12_secrets" not in live(branch_patterns_declared=True)


def test_required_is_recorded_verbatim_so_a_rule_can_see_adoption() -> None:
    facts = gather_facts(
        project="p",
        required=("00_build", "40_test"),
        verdict=None,
        archetypes=(),
        features_absent=(),
        has_changelog=True,
        baseline_files_present=(),
        adr_prefixes=("feat/", "story/"),
    )
    assert facts.required == ("00_build", "40_test")
    assert facts.live == ("00_build", "40_test")
    assert facts.adr_prefixes == ("feat/", "story/")


def test_archetype_rules_stay_silent_when_21_archetype_is_not_adopted() -> None:
    """A missing archetype feature only "fails closed" where 21_archetype actually runs.

    Reproduces PR #207's blocker: with archetypes declared but 21_archetype absent from
    [checks].required, the advisor used to claim the gate would catch a missing feature in
    the same breath as reporting 21_archetype was not required.
    """
    facts = _facts(
        archetypes=("web-api",),
        features_absent=(HEALTH, USAGE),
        recommended=("21_archetype",),
    )
    advice = advise(facts)
    assert _ids(advice.approaches) == ["a_playbook", "a_recommended"]
    rendered = render(advice)
    assert "21_archetype fails closed" not in rendered
    assert "21_archetype are not required here" in rendered

    # adopted ⇒ both rules speak again
    adopted = advise(
        _facts(archetypes=("web-api",), features_absent=(HEALTH, USAGE), live=("21_archetype",))
    )
    assert _ids(adopted.approaches) == [
        "a_web_api_health",
        "a_archetype_features",
        "a_playbook",
    ]


def test_no_rule_claims_a_check_fails_closed_unless_that_check_is_live() -> None:
    """The sweep, as an executable invariant: a rule whose text says a named check "fails
    closed" / "requires" / "ratchets" may not fire when that check is absent from ``live``."""
    nothing_adopted = _facts(
        archetypes=("web-api", "web-app"),
        features_absent=(HEALTH, USAGE),
        noop=("15_a11y",),
        failing=(("50_security", "fail"),),
        ratchets_without_baseline=(),
        recommended=("21_archetype", "12_secrets"),
        branch="main",
        changed=("src/a.py",),
        changed_src=("src/a.py",),
        enforcement="manual",
        stakes="high",
    )
    advice = advise(nothing_adopted)
    fired = advice.questions + advice.approaches
    for check in ("08_branch", "11_changelog", "13_adr", "21_archetype", "40_test"):
        for line in fired:
            assert f"{check} fails closed" not in line.text, line.rule
            assert f"{check} requires" not in line.text, line.rule
            assert f"{check} ratchets" not in line.text, line.rule
    # what remains is grounded: the verdict's own failure, the hollow check that really ran,
    # the playbook (harness prose, always available) and the adoption offer
    assert _ids(advice.questions) == ["q_enforcement_off", "q_a11y_hollow_web_app", "q_reviewer"]
    assert _ids(advice.approaches) == ["a_failing_gate", "a_playbook", "a_recommended"]


def test_heavy_field_is_recorded_and_only_the_declared_lane_is_promised() -> None:
    facts = gather_facts(
        project="p",
        required=("00_build", "60_mutation"),
        verdict=None,
        heavy=("60_mutation",),
        archetypes=(),
        features_absent=(),
        has_changelog=True,
        baseline_files_present=(),
        stakes="high",
        reviewer="ana",
    )
    assert facts.heavy == ("60_mutation",)
    assert advise(facts).approaches[-1].text == (
        "stakes are high ⇒ run the heavy lane (verify.sh --heavy: 60_mutation) before the PR,"
        " not just the fast gate"
    )
