"""Approach advisor — the right approaches and the right questions, before building.

The gate decides whether a change was built *right*; nothing decides whether the agent
is about to build the *right thing the right way*. This module answers that from facts
already on disk — the declared archetypes, the last verdict's failing and hollow checks,
the SWE-state lacks, the branch and its diff, whether enforcement is on — as two lists:
**questions** the agent should ask the human before proceeding, and **approaches** that
fit this change. Every line is a deterministic rule keyed on facts and cites the check,
SPEC or ADR it comes from (#32).

It mirrors the agent-enhancement recommender (ADR-0037): the rules are **data** — a
frozen catalog, each rule a ``when`` predicate over :class:`Facts`, its text and its
``source`` — and the module is **advisory, never a gate**: it proposes, the human
decides. No model, no score, no ranking beyond one fixed order (questions first, then
approaches, each in catalog order). Where the record says nothing it says "no advice"
rather than inventing some.

Pure: :func:`gather_facts` normalises already-read primitives; ``advise.sh`` is the
composition root that reads them. Fan-out is held at the coupling baseline (2): the
adoption vocabulary from :mod:`meta_harness.adopt` and the pass/fail classification from
:mod:`meta_harness.verdict` — the same two seams :mod:`meta_harness.swe_state` uses, so
the advisor and the SWE-state report classify a lack identically.
See docs/specs/SPEC-approach-advisor.md and ADR-0072.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import asdict, dataclass

from meta_harness.adopt import RATCHET_BASELINES, plan_adoption
from meta_harness.verdict import Verdict, is_failing

QUESTION = "question"
APPROACH = "approach"
#: What the advisor says when the record says nothing (never gated, no archetypes).
NO_FACTS_NOTE = "no advice: never gated, no archetypes"
#: The checks that are non-regression ratchets: a failure means fix the design, never the
#: baseline (ADR-0022, ADR-0029, ADR-0031, ADR-0038, ADR-0041).
RATCHETS: tuple[str, ...] = (
    "32_complexity",
    "33_coupling",
    "45_docstrings",
    "40_test",
    "60_mutation",
)
#: Branch prefixes that are work branches under Gitflow-lite (ADR-0021); anything else with
#: changes in the tree earns a question.
WORK_BRANCH_PREFIXES: tuple[str, ...] = (
    "feat/",
    "fix/",
    "docs/",
    "test/",
    "chore/",
    "refactor/",
    "perf/",
    "ci/",
    "hotfix/",
)
#: Where each ``unreadable`` bucket's fact lives, so a question names what actually broke
#: rather than a fixed pair of files.
UNREADABLE_SOURCES: Mapping[str, str] = {
    "config": "borromeanrings.toml",
    "charter": "borromeanrings.toml [charter]",
    "verdict": ".meta-harness/last_verdict.json",
    "archetypes": "the working tree the archetype evaluation walked",
}
_NOOP = "noop"
_A11Y = "15_a11y"
_ARCHETYPE = "21_archetype"
_HEALTH = "health_endpoint_declared"
_ADR_DIR = "docs/adr"
_CHANGELOG = "CHANGELOG.md"


@dataclass(frozen=True)
class FeatureGap:
    """One archetype feature absent from the project, carried across the seam as data."""

    feature_id: str
    title: str
    why: str


@dataclass(frozen=True)
class Facts:
    """Everything a rule may key on — already read, already classified, nothing guessed.

    ``required`` is the project's required ∪ heavy set; ``live`` narrows it to the checks
    whose own opt-in sub-rule is also on (``08_branch`` needs declared branch patterns,
    ``11_changelog`` needs the entry-on-source-change rule). A rule that asserts what a
    check will do must key on ``live``: citing a check this project has not adopted, or
    whose rule is switched off, would be the over-claim the gate exists to prevent.
    """

    project: str
    gated: bool
    archetypes: tuple[str, ...]
    failing: tuple[tuple[str, str], ...]
    noop: tuple[str, ...]
    ratchets_without_baseline: tuple[str, ...]
    recommended: tuple[str, ...]
    features_absent: tuple[FeatureGap, ...]
    required: tuple[str, ...]
    heavy: tuple[str, ...]
    live: tuple[str, ...]
    adr_prefixes: tuple[str, ...]
    branch: str
    changed: tuple[str, ...]
    changed_src: tuple[str, ...]
    changed_tests: bool
    changed_adr: bool
    changed_changelog: bool
    enforcement: str
    stakes: str
    reviewer: str
    unreadable: tuple[str, ...]


@dataclass(frozen=True)
class Rule:
    """One advisory rule: fires when ``when(facts)`` holds; cites where it comes from."""

    id: str
    kind: str
    when: Callable[[Facts], bool]
    text: str
    source: str


@dataclass(frozen=True)
class Line:
    """One rendered line of advice: the rule that produced it, its text and its source."""

    rule: str
    text: str
    source: str


@dataclass(frozen=True)
class Advice:
    """The advisor's answer for one project: questions first, then approaches."""

    facts: Facts
    questions: tuple[Line, ...]
    approaches: tuple[Line, ...]
    note: str


# --- gathering ---------------------------------------------------------------------------------


def _under(path: str, directory: str) -> bool:
    """Boundary-safe prefix test: ``src/a.py`` is under ``src``; ``src_gen/a.py`` is not."""
    return path == directory or path.startswith(directory + "/")


@dataclass(frozen=True)
class _Diff:
    """What the changed paths say: source touched, tests / ADR / changelog touched."""

    src: tuple[str, ...]
    tests: bool
    adr: bool
    changelog: bool


def _diff(changed: Sequence[str], src_dir: str, tests_dir: str) -> _Diff:
    return _Diff(
        tuple(p for p in changed if _under(p, src_dir)),
        any(_under(p, tests_dir) for p in changed),
        any(_under(p, _ADR_DIR) for p in changed),
        _CHANGELOG in changed,
    )


def _lacking(
    required: Sequence[str], verdict: Verdict | None
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """``(failing, noop)`` among the required checks the last verdict recorded."""
    recorded = dict(verdict.checks) if verdict is not None else {}
    statuses = [(c, recorded[c]) for c in required if c in recorded]
    failing = tuple((c, s) for c, s in statuses if is_failing(s))
    return failing, tuple(c for c, s in statuses if s == _NOOP)


def _live(
    required: Sequence[str], *, branch_patterns_declared: bool, changelog_entry_on_src: bool
) -> tuple[str, ...]:
    """The required checks actually in force: adopted, and their opt-in sub-rule on."""
    sub_rule_on = {
        "08_branch": branch_patterns_declared,
        "11_changelog": changelog_entry_on_src,
    }
    return tuple(check for check in required if sub_rule_on.get(check, True))


def _ratchets_without_baseline(
    required: Sequence[str], baseline_files_present: Collection[str]
) -> tuple[str, ...]:
    return tuple(
        c
        for c in required
        if c in RATCHET_BASELINES and RATCHET_BASELINES[c] not in baseline_files_present
    )


def gather_facts(
    *,
    project: str,
    required: Sequence[str],
    verdict: Verdict | None,
    heavy: Sequence[str] = (),
    archetypes: Sequence[str],
    features_absent: Sequence[FeatureGap],
    has_changelog: bool,
    baseline_files_present: Collection[str],
    branch: str = "",
    changed: Sequence[str] = (),
    src_dir: str = "src",
    tests_dir: str = "tests",
    branch_patterns_declared: bool = False,
    changelog_entry_on_src: bool = False,
    adr_prefixes: Sequence[str] = (),
    enforcement: str = "",
    stakes: str = "",
    reviewer: str = "",
    unreadable: Sequence[str] = (),
) -> Facts:
    """Normalise already-read primitives into :class:`Facts` (pure; SPEC §4.1).

    A required check is *failing* when the last verdict recorded a status
    :func:`~meta_harness.verdict.is_failing` says fails, *noop* when it recorded ``noop``;
    a check the verdict says nothing about is neither (never gated ⇒ nothing lacking).

    ``branch_patterns_declared`` / ``changelog_entry_on_src`` / ``adr_prefixes`` come from
    the same spine the checks read, so a rule only claims a check will fail when that
    check is adopted here **and** its own opt-in rule is on.
    """
    failing, noop = _lacking(required, verdict)
    diff = _diff(changed, src_dir, tests_dir)
    live = _live(
        required,
        branch_patterns_declared=branch_patterns_declared,
        changelog_entry_on_src=changelog_entry_on_src,
    )
    recommended = (
        ()
        if "config" in unreadable
        else plan_adoption(tuple(required), has_changelog=has_changelog).add_checks
    )
    return Facts(
        project=project,
        gated=verdict is not None,
        archetypes=tuple(archetypes),
        failing=failing,
        noop=noop,
        ratchets_without_baseline=_ratchets_without_baseline(required, baseline_files_present),
        recommended=recommended,
        features_absent=tuple(features_absent),
        required=tuple(required),
        heavy=tuple(heavy),
        live=live,
        adr_prefixes=tuple(adr_prefixes),
        branch=branch,
        changed=tuple(changed),
        changed_src=diff.src,
        changed_tests=diff.tests,
        changed_adr=diff.adr,
        changed_changelog=diff.changelog,
        enforcement=enforcement,
        stakes=stakes,
        reviewer=reviewer,
        unreadable=tuple(unreadable),
    )


# --- the catalog ----------------------------------------------------------------------------


def _a11y_hollow_web_app(f: Facts) -> bool:
    return "web-app" in f.archetypes and _A11Y in f.noop


def _noop_other(f: Facts) -> tuple[str, ...]:
    return tuple(c for c in f.noop if not (c == _A11Y and _a11y_hollow_web_app(f)))


def _archetype_gate_on(f: Facts) -> bool:
    """Is ``21_archetype`` actually in force here? It is opt-in like every other check, so a
    rule may not say a missing feature "fails closed" unless this project runs it."""
    return _ARCHETYPE in f.live


def _web_api_health(f: Facts) -> bool:
    return (
        _archetype_gate_on(f)
        and "web-api" in f.archetypes
        and any(g.feature_id == _HEALTH for g in f.features_absent)
    )


def _features_other(f: Facts) -> tuple[FeatureGap, ...]:
    return tuple(
        g for g in f.features_absent if not (g.feature_id == _HEALTH and _web_api_health(f))
    )


def _failing_ratchets(f: Facts) -> tuple[tuple[str, str], ...]:
    return tuple(pair for pair in f.failing if pair[0] in RATCHETS)


def _failing_other(f: Facts) -> tuple[tuple[str, str], ...]:
    return tuple(pair for pair in f.failing if pair[0] not in RATCHETS)


def _on_work_branch(f: Facts) -> bool:
    return not f.branch or f.branch.startswith(WORK_BRANCH_PREFIXES)


def _enforcement_off(f: Facts) -> bool:
    return f.gated and f.enforcement in ("manual", "partial")


CATALOG: tuple[Rule, ...] = (
    Rule(
        "q_never_gated",
        QUESTION,
        lambda f: not f.gated and bool(f.archetypes),
        "this project has never been gated — run verify.sh before starting, or is the gate"
        " deliberately off?",
        "SPEC-self-status.md",
    ),
    Rule(
        "q_unreadable",
        QUESTION,
        lambda f: bool(f.unreadable),
        "{unreadable} could not be read — fix the record ({unreadable_where}) before"
        " building on it?",
        "SPEC-swe-state.md",
    ),
    Rule(
        "q_enforcement_off",
        QUESTION,
        _enforcement_off,
        "enforcement is {enforcement_upper} here — the gate runs only when invoked; should the"
        " hooks be wired before you begin (the user's decision, not yours)?",
        "SPEC-self-status.md",
    ),
    Rule(
        "q_no_archetype",
        QUESTION,
        lambda f: f.gated and not f.archetypes,
        "no archetype is declared — what kind of application is this (cli, library,"
        " web-api, web-app, ml, embedded, data-pipeline)? [project].archetypes is the"
        " declaration 21_archetype reads; while it is empty that dimension is off",
        "21_archetype",
    ),
    Rule(
        "q_a11y_hollow_web_app",
        QUESTION,
        _a11y_hollow_web_app,
        "the last verdict is hollow on 15_a11y for a web-app — is there really no HTML"
        " here, or does [a11y] / the tree not match reality?",
        _A11Y,
    ),
    Rule(
        "q_hollow_checks",
        QUESTION,
        lambda f: bool(_noop_other(f)),
        "{noop_other} inspected NOTHING last run — is there truly nothing to inspect, or should"
        " each be pointed at something (or dropped from [checks].required)?",
        "ADR-0049",
    ),
    Rule(
        "q_reviewer",
        QUESTION,
        lambda f: bool(f.stakes) and not f.reviewer,
        "stakes are {stakes} and no reviewer is named — who reviews and merges this"
        " (merge.sh is explicit and human)?",
        "ADR-0007",
    ),
    Rule(
        "q_branch",
        QUESTION,
        lambda f: bool(f.changed) and not _on_work_branch(f) and "08_branch" in f.live,
        "you are on '{branch}' with changes in the tree — should this work be on a feat/ or"
        " fix/ branch (08_branch fails closed on protected branches)?",
        "08_branch",
    ),
    Rule(
        "a_failing_ratchet",
        APPROACH,
        lambda f: bool(_failing_ratchets(f)),
        "a ratchet is failing ({failing_ratchets}) ⇒ fix the design, never"
        " the baseline: split the module, reach siblings through one seam, test the branch",
        "ADR-0041",
    ),
    Rule(
        "a_failing_gate",
        APPROACH,
        lambda f: bool(_failing_other(f)),
        "the last verdict fails on {failing_other} ⇒ the gate is fail-closed: fix those"
        " findings before adding anything new",
        "ADR-0049",
    ),
    Rule(
        "a_ratchet_baseline",
        APPROACH,
        lambda f: bool(f.ratchets_without_baseline),
        "ratchet(s) {ratchets} have no baseline ⇒ seed it from current state"
        " (adopt.sh) so the line holds; never pick a target",
        "ADR-0041",
    ),
    Rule(
        "a_spec_and_adr_first",
        APPROACH,
        lambda f: (
            bool(f.adr_prefixes)
            and f.branch.startswith(tuple(f.adr_prefixes))
            and bool(f.changed_src)
            and not f.changed_adr
            and "13_adr" in f.live
        ),
        "new surface on '{branch}' touches {changed_src} and no docs/adr/ file ⇒ decide first,"
        " on the record: a SPEC under docs/specs and an ADR under docs/adr before the code"
        " (13_adr fails closed without one)",
        "13_adr",
    ),
    Rule(
        "a_test_first",
        APPROACH,
        lambda f: bool(f.changed_src) and not f.changed_tests and "40_test" in f.live,
        "{changed_src} changed with no test change ⇒ write the failing test first and show it"
        " fail (40_test ratchets coverage; a test that passes regardless is worse than none)",
        "40_test",
    ),
    Rule(
        "a_changelog_with_change",
        APPROACH,
        lambda f: bool(f.changed_src) and not f.changed_changelog and "11_changelog" in f.live,
        "{changed_src} changed and CHANGELOG.md did not ⇒ write the [Unreleased] entry with"
        " the change, not at release time (11_changelog requires it on a source change)",
        "11_changelog",
    ),
    Rule(
        "a_web_api_health",
        APPROACH,
        _web_api_health,
        "archetype web-api with no health route ⇒ add /livez and /readyz before the feature"
        " (21_archetype fails closed on health_endpoint_declared)",
        "SPEC-archetypes.md",
    ),
    Rule(
        "a_archetype_features",
        APPROACH,
        lambda f: _archetype_gate_on(f) and bool(_features_other(f)),
        "archetype(s) {archetypes} lack required feature(s) {features_other} ⇒ add them"
        " before the feature; 21_archetype fails closed until they exist",
        "21_archetype",
    ),
    Rule(
        "a_playbook",
        APPROACH,
        lambda f: bool(f.archetypes),
        "archetype(s) {archetypes} declared ⇒ read the catalog playbook for each"
        " (meta_harness.archetypes.CATALOG[name].playbook) before designing the change",
        "ADR-0062",
    ),
    Rule(
        "a_recommended",
        APPROACH,
        lambda f: bool(f.recommended),
        "RECOMMENDED checks {recommended} are not required here ⇒ adopt.sh adds them"
        " and seeds their baselines; propose it, do not apply it silently",
        "ADR-0041",
    ),
    Rule(
        "a_heavy_lane_high_stakes",
        APPROACH,
        lambda f: bool(f.stakes) and f.stakes.lower() != "low" and bool(f.heavy),
        "stakes are {stakes} ⇒ run the heavy lane (verify.sh --heavy: {heavy}) before the PR,"
        " not just the fast gate",
        "ADR-0033",
    ),
)


# --- advising -----------------------------------------------------------------------------------


def _gap_text(gap: FeatureGap) -> str:
    return f"{gap.feature_id} — {gap.title}" + (f" ({gap.why})" if gap.why else "")


def _fields(f: Facts) -> Mapping[str, str]:
    """The template vocabulary: every list pre-joined so a rule's text is one format call."""
    pairs = ", ".join
    return {
        "archetypes": pairs(f.archetypes),
        "failing_ratchets": pairs(f"{c} ({s})" for c, s in _failing_ratchets(f)),
        "failing_other": pairs(f"{c} ({s})" for c, s in _failing_other(f)),
        "noop_other": pairs(_noop_other(f)),
        "ratchets": pairs(f.ratchets_without_baseline),
        "recommended": pairs(f.recommended),
        "features_other": pairs(_gap_text(g) for g in _features_other(f)),
        "branch": f.branch,
        "changed_src": pairs(f.changed_src),
        "heavy": pairs(f.heavy),
        "unreadable_where": pairs(
            dict.fromkeys(UNREADABLE_SOURCES.get(name, name) for name in f.unreadable)
        ),
        "enforcement_upper": f.enforcement.upper(),
        "stakes": f.stakes,
        "unreadable": pairs(f.unreadable),
    }


def _no_facts(f: Facts) -> bool:
    """Does the record say nothing at all? Declared stakes count as something to say."""
    return not f.gated and not f.archetypes and not f.unreadable and not f.changed and not f.stakes


def advise(facts: Facts) -> Advice:
    """Apply the catalog: questions first, then approaches, each in catalog order (pure).

    No facts at all (never gated, no archetypes, nothing unreadable, nothing changed) ⇒
    both lists empty and ``note`` says so — the record says nothing, so neither does the
    advisor.
    """
    if _no_facts(facts):
        return Advice(facts, (), (), NO_FACTS_NOTE)
    fields = _fields(facts)
    fired = [
        Line(rule.id, rule.text.format_map(fields), rule.source)
        for rule in CATALOG
        if rule.when(facts)
    ]
    kind = {rule.id: rule.kind for rule in CATALOG}
    return Advice(
        facts,
        tuple(line for line in fired if kind[line.rule] == QUESTION),
        tuple(line for line in fired if kind[line.rule] == APPROACH),
        "",
    )


# --- rendering ----------------------------------------------------------------------------------


def _section(title: str, lines: Sequence[Line]) -> list[str]:
    out = [title]
    out += [f"  {n}. {line.text}  [{line.source}]" for n, line in enumerate(lines, start=1)]
    return out if lines else out + ["  (none)"]


def _facts_line(f: Facts) -> str:
    join = ", ".join
    return (
        f"Facts: gated={'yes' if f.gated else 'no'} · archetypes: {join(f.archetypes) or 'none'}"
        f" · branch: {f.branch or 'none'} · enforcement: {f.enforcement or 'unknown'}"
        f" · failing: {join(f'{c} ({s})' for c, s in f.failing) or 'none'}"
        f" · noop: {join(f.noop) or 'none'} · changed: {len(f.changed)} path(s)"
        f" · stakes: {f.stakes or '(no charter)'}"
    )


def render(advice: Advice) -> str:
    """The advice as plain text: two numbered sections, the facts line, the fixed order."""
    f = advice.facts
    name = f.project.rstrip("/").rsplit("/", maxsplit=1)[-1]
    head = [f"borromeanRings — approach advice for {name}   (advisory; never a gate)"]
    body = (
        [[f"  {advice.note}"]]
        if advice.note
        else [
            _section("Questions to ask before proceeding", advice.questions),
            _section("Approaches that fit this change", advice.approaches),
        ]
    )
    tail = [
        _facts_line(f),
        "Order: fixed — questions, then approaches, each in catalog order; no score, no ranking",
    ]
    return "\n\n".join("\n".join(block) for block in [head, *body, tail]) + "\n"


def to_json(advice: Advice) -> str:
    """The advice as JSON (``asdict``; tuples become lists)."""
    return json.dumps(asdict(advice), indent=2, ensure_ascii=False) + "\n"
