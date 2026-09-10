"""Unit tests for the predicate lint (meta_harness.predicates).

Predicates are the checkable statements this repo's documents make: SPEC ``Contract`` /
``Guarantees`` / ``Acceptance`` bullets, ADR ``Consequences`` bullets phrased as
obligations, and issue-form task-list items. Two defects are mechanical: a hedge word
that makes a predicate a matter of opinion, and a SPEC nothing points back to (an orphan).
See docs/specs/SPEC-predicates.md and ADR-0064.
"""

from __future__ import annotations

import pytest

from meta_harness import predicates as mod
from meta_harness.predicates import (
    HEDGES,
    Document,
    Finding,
    Predicate,
    Report,
    extract,
    hedged,
    kind_of,
    lint,
    render,
)

SPEC = """\
# SPEC — Example

## Problem
Prose with as needed in it is not a predicate.

## Contract
`23_predicates` fails closed on any hedge.
- The check fails on a hedged predicate.
- A wrapped item
  continues on the next line and mentions as needed here.
1. Numbered items count too.
   - nested bullets as well, verified by test_example.py
```
- inside a fence: reviewed appropriately (skipped)
```

## Design
- Design bullets are not predicates, even if reasonable.

## Guarantees
- **Deterministic** — the same input yields the same output.
"""


def _doc(path: str, text: str) -> Document:
    return Document(path=path, text=text)


# ---------------------------------------------------------------- classification


def test_kind_of_classifies_by_filename_only() -> None:
    assert kind_of("docs/specs/SPEC-x.md") == "spec"
    assert kind_of("docs/adr/0064-predicate-lint.md") == "adr"
    assert kind_of(".github/ISSUE_TEMPLATE/feature_request.yml") == "issue"
    assert kind_of(".github/ISSUE_TEMPLATE/bug.yaml") == "issue"
    assert kind_of(".github/ISSUE_TEMPLATE/feature_request.md") == "issue"
    assert kind_of("docs/adr/README.md") is None
    assert kind_of("docs/specs/notes.md") is None
    assert kind_of("docs/adr/123-short.md") is None
    assert kind_of("other/forms.yml") == "issue"


# ---------------------------------------------------------------- extraction


def test_spec_predicates_come_only_from_predicate_sections() -> None:
    preds = extract(_doc("docs/specs/SPEC-x.md", SPEC))
    texts = [p.text for p in preds]
    assert texts == [
        "The check fails on a hedged predicate.",
        "A wrapped item continues on the next line and mentions as needed here.",
        "Numbered items count too.",
        "nested bullets as well, verified by test_example.py",
        "**Deterministic** — the same input yields the same output.",
    ]
    assert [p.line for p in preds] == [8, 9, 11, 12, 21]
    assert all(p.kind == "spec" and p.path == "docs/specs/SPEC-x.md" for p in preds)


@pytest.mark.parametrize(
    "heading",
    [
        "## Contract",
        "## 3. Contract (the seam)",
        '## 7. Contract / definition of "done"',
        "## Contracts (`meta_harness.layout`, pure + unit-tested)",
        "## Acceptance criteria",
        "## Acceptance",
        "## 2.1 Guarantees: what holds",
        "### Contract",
    ],
)
def test_heading_normalization_selects_predicate_sections(heading: str) -> None:
    text = f"# T\n\n{heading}\n- item one\n"
    assert [p.text for p in extract(_doc("SPEC-h.md", text))] == ["item one"]


@pytest.mark.parametrize("heading", ["## Tier A contract", "## Rules", "## Contracting"])
def test_non_predicate_headings_are_ignored(heading: str) -> None:
    text = f"# T\n\n{heading}\n- item one\n"
    assert extract(_doc("SPEC-h.md", text)) == ()


def test_section_ends_at_same_or_higher_heading_but_not_lower() -> None:
    text = "## Contract\n- a\n### Sub\n- b\n## Other\n- c\n# Top\n- d\n"
    assert [p.text for p in extract(_doc("SPEC-s.md", text))] == ["a", "b"]


def test_higher_heading_closes_an_open_section() -> None:
    text = "### Contract\n- a\n## Other\n- b\n"
    assert [p.text for p in extract(_doc("SPEC-s.md", text))] == ["a"]


def test_list_item_continuation_stops_at_blank_or_unindented_line() -> None:
    text = "## Contract\n- first\n  more\n\n  not joined\nplain prose\n- second\n"
    assert [p.text for p in extract(_doc("SPEC-c.md", text))] == ["first more", "second"]


def test_fenced_block_inside_section_is_skipped_and_closed() -> None:
    text = "## Contract\n```\n- fenced\n```\n- real\n~~~\n- tilde fenced\n~~~\n"
    assert [p.text for p in extract(_doc("SPEC-f.md", text))] == ["real"]


def test_adr_consequences_only_obligation_bullets() -> None:
    adr = (
        "# ADR-0001\n\n## Decision\n- must not count here\n\n## Consequences\n"
        "- (+) A nice property, phrased loosely.\n"
        "- (−) The file MUST never be edited by hand.\n"
        "- (−) Callers shall retry.\n"
        "- (−) It mustard the sandwich.\n"
    )
    preds = extract(_doc("docs/adr/0001-x.md", adr))
    assert [p.text for p in preds] == [
        "(−) The file MUST never be edited by hand.",
        "(−) Callers shall retry.",
    ]
    assert [p.line for p in preds] == [8, 9]
    assert {p.kind for p in preds} == {"adr"}


def test_issue_form_checkboxes_anywhere_and_placeholders_skipped() -> None:
    form = (
        "name: Feature\nbody:\n  - type: textarea\n    attributes:\n      value: |\n"
        "        - [ ] ...\n        - [ ] …\n        - [x] Done item\n"
        "        - [ ] Fails closed when the tool is missing\n"
        "        - plain bullet is not a task\n"
    )
    preds = extract(_doc(".github/ISSUE_TEMPLATE/f.yml", form))
    assert [(p.line, p.text) for p in preds] == [
        (8, "Done item"),
        (9, "Fails closed when the tool is missing"),
    ]
    assert {p.kind for p in preds} == {"issue"}


def test_unclassified_document_yields_nothing() -> None:
    assert extract(_doc("docs/notes.md", "## Contract\n- x\n")) == ()


def test_extract_is_deterministic() -> None:
    doc = _doc("docs/specs/SPEC-x.md", SPEC)
    assert extract(doc) == extract(doc)


# ---------------------------------------------------------------- hedges


@pytest.mark.parametrize(
    ("text", "hedge"),
    [
        ("The output is reviewed appropriately.", "appropriately"),
        ("Rotate keys as needed.", "as needed"),
        ("Rotate keys  AS   Needed.", "as needed"),
        ("Log a reasonable amount.", "reasonable"),
        ("Supports json, yaml, etc.", "etc"),
        ("Fast and/or cheap.", "and/or"),
        ("Uses best judgment.", "best judgment"),
        ("Tokens (as required) are read.", "as required"),
    ],
)
def test_hedged_names_the_offending_term(text: str, hedge: str) -> None:
    assert hedged(text) == hedge


@pytest.mark.parametrize(
    "text",
    [
        "A review record exists under `.meta-harness/`.",
        "Writes are best-effort: a failure never turns PASS into FAIL.",
        "An improperly formed receipt fails.",
        "The etcd endpoint is pinned.",
        "",
    ],
)
def test_checkable_predicates_are_not_hedged(text: str) -> None:
    assert hedged(text) is None


def test_hedged_reports_the_first_term_by_position() -> None:
    assert hedged("roughly done, then reviewed appropriately") == "roughly"


def test_extra_hedges_extend_the_builtin_list() -> None:
    assert hedged("It is fluffy.") is None
    assert hedged("It is fluffy.", extra=("fluffy",)) == "fluffy"
    assert hedged("Reviewed appropriately.", extra=("fluffy",)) == "appropriately"
    assert hedged("It is  very  fluffy.", extra=("very fluffy",)) == "very fluffy"


def test_extra_hedge_is_matched_as_a_whole_word() -> None:
    assert hedged("It is fluffyish.", extra=("fluffy",)) is None


def test_builtin_hedge_list_is_fixed_and_hedged_itself() -> None:
    assert "appropriately" in HEDGES and "as needed" in HEDGES and "best effort" in HEDGES
    assert len(HEDGES) == len(set(HEDGES))
    for term in HEDGES:
        assert hedged(f"Do this {term} today.") == term


# ---------------------------------------------------------------- orphans


def _spec(name: str, body: str) -> Document:
    return _doc(f"docs/specs/{name}", f"# S\n\n## Contract\n- {body}\n")


KNOWN_CHECKS = frozenset({"05_hygiene", "23_predicates"})
KNOWN_TESTS = frozenset({"test_predicates.py"})


def test_spec_referencing_a_known_check_is_not_an_orphan() -> None:
    docs = [_spec("SPEC-a.md", "Enforced by `23_predicates`.")]
    assert mod.orphans(docs, known_checks=KNOWN_CHECKS, known_tests=KNOWN_TESTS) == ()


def test_spec_referencing_a_known_test_or_issue_is_not_an_orphan() -> None:
    by_test = _spec("SPEC-t.md", "Verified by test_predicates.py.")
    by_issue = _spec("SPEC-i.md", "Tracks issue #174.")
    assert (
        mod.orphans([by_test, by_issue], known_checks=KNOWN_CHECKS, known_tests=KNOWN_TESTS) == ()
    )


def test_reference_anywhere_in_the_spec_counts() -> None:
    doc = _doc("docs/specs/SPEC-x.md", "# S\nVerified by test_predicates.py\n## Contract\n- a\n")
    assert mod.orphans([doc], known_checks=KNOWN_CHECKS, known_tests=KNOWN_TESTS) == ()


def test_spec_without_references_is_an_orphan() -> None:
    docs = [_spec("SPEC-b.md", "Something holds."), _spec("SPEC-a.md", "Something else.")]
    assert mod.orphans(docs, known_checks=KNOWN_CHECKS, known_tests=KNOWN_TESTS) == (
        "docs/specs/SPEC-a.md",
        "docs/specs/SPEC-b.md",
    )


def test_unresolvable_references_do_not_rescue_a_spec() -> None:
    """The 4D lesson: an id-shaped token that resolves to nothing must count for nothing."""
    ghost_check = _spec("SPEC-g.md", "Enforced by `99_ghost`.")
    ghost_test = _spec("SPEC-h.md", "Verified by test_ghost.py.")
    wildcard = _spec("SPEC-w.md", "Enforced by all checks and #0.")
    result = mod.orphans(
        [ghost_check, ghost_test, wildcard], known_checks=KNOWN_CHECKS, known_tests=KNOWN_TESTS
    )
    assert result == ("docs/specs/SPEC-g.md", "docs/specs/SPEC-h.md", "docs/specs/SPEC-w.md")


def test_check_id_must_be_a_whole_token() -> None:
    assert mod.orphans(
        [_spec("SPEC-p.md", "see x23_predicates_y")],
        known_checks=KNOWN_CHECKS,
        known_tests=KNOWN_TESTS,
    ) == ("docs/specs/SPEC-p.md",)


def test_only_specs_are_subject_to_the_orphan_rule() -> None:
    adr = _doc("docs/adr/0001-x.md", "## Consequences\n- must hold\n")
    form = _doc(".github/ISSUE_TEMPLATE/f.yml", "- [ ] item\n")
    assert mod.orphans([adr, form], known_checks=KNOWN_CHECKS, known_tests=KNOWN_TESTS) == ()


def test_orphan_detector_is_not_vacuous(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation-driven: replace the detector with one that finds nothing and prove the
    suite notices. A detector that never reports is exactly the failure 4D shipped;
    this test fails if the assertions above would let such a mutant through."""
    monkeypatch.setattr(mod, "orphans", lambda *a, **k: ())
    with pytest.raises(AssertionError):
        test_spec_without_references_is_an_orphan()
    with pytest.raises(AssertionError):
        test_unresolvable_references_do_not_rescue_a_spec()
    # And a mutant that reports everything is caught by the negative controls.
    monkeypatch.setattr(mod, "orphans", lambda docs, **k: tuple(d.path for d in docs))
    with pytest.raises(AssertionError):
        test_spec_referencing_a_known_check_is_not_an_orphan()


# ---------------------------------------------------------------- lint + render


def test_lint_collects_predicates_findings_and_orphans() -> None:
    hedged_spec = _spec("SPEC-a.md", "Rotate as needed; enforced by `05_hygiene`.")
    orphan_spec = _spec("SPEC-b.md", "A clean predicate with no reference.")
    report = lint(
        [hedged_spec, orphan_spec],
        known_checks=KNOWN_CHECKS,
        known_tests=KNOWN_TESTS,
    )
    assert isinstance(report, Report)
    assert [p.path for p in report.predicates] == ["docs/specs/SPEC-a.md", "docs/specs/SPEC-b.md"]
    assert report.findings == (
        Finding(
            Predicate(
                path="docs/specs/SPEC-a.md",
                line=4,
                text="Rotate as needed; enforced by `05_hygiene`.",
                kind="spec",
            ),
            "as needed",
        ),
    )
    assert report.orphans == ("docs/specs/SPEC-b.md",)
    assert report.ok is False


def test_lint_extra_hedges_and_reference_rule_off() -> None:
    doc = _spec("SPEC-a.md", "It is fluffy.")
    report = lint(
        [doc], known_checks=frozenset(), known_tests=frozenset(), extra_hedges=("fluffy",)
    )
    assert [f.hedge for f in report.findings] == ["fluffy"]
    assert report.orphans == ("docs/specs/SPEC-a.md",)
    off = lint([doc], known_checks=frozenset(), known_tests=frozenset(), require_reference=False)
    assert off.orphans == () and off.findings == ()
    assert off.ok is True


def test_lint_with_no_predicates_is_empty() -> None:
    report = lint(
        [_doc("docs/notes.md", "- x\n")], known_checks=frozenset(), known_tests=frozenset()
    )
    assert report.predicates == () and report.ok is True


def test_render_failure_names_file_line_predicate_and_hedge() -> None:
    report = lint(
        [_spec("SPEC-a.md", "Reviewed appropriately."), _spec("SPEC-b.md", "Fine; see #174.")],
        known_checks=frozenset(),
        known_tests=frozenset(),
    )
    text = render(report)
    assert "docs/specs/SPEC-a.md:4 — Reviewed appropriately. — appropriately" in text
    assert "1 hedged predicate" in text
    assert "ORPHAN" in text and "docs/specs/SPEC-a.md" in text.split("ORPHAN", 1)[1]
    assert "SPEC-b.md" not in text.split("ORPHAN", 1)[1]


def test_render_pass_reports_counts() -> None:
    report = lint(
        [
            _spec("SPEC-a.md", "Fine; see #174."),
            _doc("docs/adr/0001-x.md", "## Consequences\n- must\n"),
        ],
        known_checks=frozenset(),
        known_tests=frozenset(),
    )
    text = render(report)
    assert "2 predicate(s)" in text and "2 document(s)" in text and "1 SPEC(s)" in text
    assert "0 hedged" in text
    assert "ORPHAN" not in text


def test_render_says_when_the_reference_rule_is_off() -> None:
    report = lint(
        [_spec("SPEC-a.md", "No reference at all.")],
        known_checks=frozenset(),
        known_tests=frozenset(),
        require_reference=False,
    )
    assert "reference rule off" in render(report)
    assert "SPEC(s) referenced" not in render(report)


@pytest.mark.parametrize(
    ("heading", "selected"),
    [
        ("## Contract:", True),
        ("## Contract: what holds", True),
        ("## Contract:X", False),
        ("## See Contract:X", False),
    ],
)
def test_colon_cuts_a_title_only_when_it_ends_a_word(heading: str, selected: bool) -> None:
    text = f"# T\n\n{heading}\n- item one\n"
    assert bool(extract(_doc("SPEC-h.md", text))) is selected


def test_spec_with_no_predicate_section_and_no_reference_is_still_an_orphan() -> None:
    """Fail-closed: a SPEC nothing points at is an orphan even if it asserts nothing."""
    doc = _doc("docs/specs/SPEC-empty.md", "# S\n\n## Problem\nProse only.\n")
    report = lint([doc], known_checks=KNOWN_CHECKS, known_tests=KNOWN_TESTS)
    assert report.predicates == ()
    assert report.orphans == ("docs/specs/SPEC-empty.md",)
    assert report.ok is False
