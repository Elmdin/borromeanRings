"""Unit tests for the citation extractor and its resolution filter.

Every real defect the review cycle caught appears here as a fixture, quoted from the
document that carried it, so the check is anchored to evidence rather than to invented
examples. The out-of-scope instances are fixtures too: a gate that implies more than it
verifies is the defect being fixed, so the boundary is asserted, not just described.

See docs/specs/SPEC-citations.md and ADR-0073.
"""

from collections.abc import Callable, Iterable

from meta_harness.citations import (
    Citation,
    citations,
    code_spans,
    heading_slugs,
    prose_lines,
    render,
    slugify,
    unresolved,
)


def _resolver(known: Iterable[str]) -> Callable[[Citation], bool]:
    """A resolver over a fixed vocabulary — the injection seam, with no filesystem."""
    vocabulary = frozenset(known)
    return lambda citation: citation.target in vocabulary


# --------------------------------------------------------------------------------------
# The real instances the review cycle found (each quoted from the offending document)
# --------------------------------------------------------------------------------------


def test_pr184_handoff_cited_on_a_base_that_lacks_it() -> None:
    """PR #184: `docs/4D-DRY-RUNS.md` cited `docs/HANDOFF.md` twice; it lived only on the
    unmerged `docs/handoff` branch."""
    text = (
        "This repository's standing rule (`CHARTER.toml` `may_not`; restated in\n"
        "`docs/HANDOFF.md` section 3) is that a signal is either a binary fact\n"
        "or a non-regression ratchet.\n"
        "\n"
        "Building it here would be speculative (`docs/HANDOFF.md` section 3 calls this\n"
        '"justified building").\n'
    )
    found = citations(text)
    assert found == (
        Citation("path", "docs/HANDOFF.md", 2, False),
        Citation("path", "docs/HANDOFF.md", 5, False),
    )
    assert unresolved(found, _resolver({"CHARTER.toml"})) == found


def test_pr195_bare_adr_numbers_absent_from_the_base() -> None:
    """PR #195: `ADR-0057`/`ADR-0061` bare in a table on a base whose ADRs stop at 0047,
    while the same document labels both correctly elsewhere."""
    text = (
        "| Agent-only critics | ADR-0057 |\n"
        "| Two-speed stewardship | ADR-0061 |\n"
        "Elsewhere the same document writes ADR-0057 (lands with #166) and\n"
        "ADR-0061 (lands with #170), which is the labelled form.\n"
    )
    found = citations(text)
    assert found == (
        Citation("adr", "ADR-0057", 1, False),
        Citation("adr", "ADR-0061", 2, False),
        Citation("adr", "ADR-0057", 3, True),
        Citation("adr", "ADR-0061", 4, True),
    )
    assert unresolved(found, _resolver({"ADR-0047"})) == (
        Citation("adr", "ADR-0057", 1, False),
        Citation("adr", "ADR-0061", 2, False),
    )


def test_pr195_checks_doc_cited_as_being_on_this_base() -> None:
    """PR #195: "the two documents disagree **on this base**" naming `docs/CHECKS.md`,
    which is not on that base at all."""
    text = "`docs/CHECKS.md` says so, and the two documents disagree **on this base**.\n"
    found = citations(text)
    assert found == (Citation("path", "docs/CHECKS.md", 1, False),)
    assert unresolved(found, _resolver({"docs/ENFORCEMENT-COVERAGE.md"})) == found


def test_pr161_and_pr168_dead_links_and_section_references() -> None:
    """PR #161 (three templates linking `docs/HANDOFF.md`) and PR #168 (a survey section
    reference), both absent from their bases."""
    text = (
        "- [ ] Read the [handoff contract](../../docs/HANDOFF.md) before starting.\n"
        "The audit cites `docs/research/AGENT-TOOLING-SURVEY.md` section 2.\n"
    )
    found = citations(text, base=".github/ISSUE_TEMPLATE")
    assert found == (
        Citation("path", "docs/HANDOFF.md", 1, False),
        Citation("path", "docs/research/AGENT-TOOLING-SURVEY.md", 2, False),
    )


def test_pr196_issue_number_confusion_is_out_of_scope() -> None:
    """PR #196: ADR-0069 cited issue `#53` for a fix that shipped in PR `#82`.

    That is GitHub state, off-machine and mutable — this check must not pretend to reach
    it. The ADR reference on the same line IS checked; the issue numbers are not.
    """
    text = "incidents (#53, the orphaned-shell bug) — ADR-0069 records the substrate.\n"
    assert citations(text) == (Citation("adr", "ADR-0069", 1, False),)


def test_pr151_unimplemented_contract_row_is_out_of_scope() -> None:
    """PR #151: a SPEC contract row promised a per-check ADR citation `describe.py` never
    derives. Every path in the row resolves; the false part is behavioural.

    This is the boundary between this gate and the `55_doc_drift` critic (ADR-0030), and
    it is asserted rather than merely documented.
    """
    text = (
        "| Skills | via frontmatter | `src/meta_harness/describe.py` |\n"
        "| Advisory lanes | via module presence | `describe.sh --readme` |\n"
    )
    found = citations(text)
    assert found == (Citation("path", "src/meta_harness/describe.py", 1, False),)
    assert unresolved(found, _resolver({"src/meta_harness/describe.py"})) == ()


# --------------------------------------------------------------------------------------
# What counts as a citation
# --------------------------------------------------------------------------------------


def test_path_kinds_anchor_line_suffix_and_dot_prefix() -> None:
    text = (
        "See `docs/CHECKS.md#enabling-checks-in-a-project` and\n"
        "`src/meta_harness/spine.py:45`, `checks/python/17_prior_art.sh:45-49`, `./verify.sh`.\n"
    )
    assert citations(text) == (
        Citation("anchor", "docs/CHECKS.md#enabling-checks-in-a-project", 1, False),
        Citation("path", "src/meta_harness/spine.py", 2, False),
        Citation("path", "checks/python/17_prior_art.sh", 2, False),
        Citation("path", "verify.sh", 2, False),
    )


def test_adr_and_check_ids_in_prose() -> None:
    text = "ADR-0043 gates it; `13_adr` and 60_mutation are the checks.\n"
    assert citations(text) == (
        Citation("adr", "ADR-0043", 1, False),
        Citation("check", "13_adr", 1, False),
        Citation("check", "60_mutation", 1, False),
    )


def test_globbed_adr_path_cites_the_record_number() -> None:
    assert citations("Rationale in `docs/adr/0043-*.md`.\n") == (
        Citation("adr", "ADR-0043", 1, False),
    )


def test_a_check_id_inside_a_path_is_read_as_the_path_only() -> None:
    assert citations("`checks/shared/13_adr.sh`\n") == (
        Citation("path", "checks/shared/13_adr.sh", 1, False),
    )


def test_link_targets_are_resolved_against_the_citing_file_directory() -> None:
    text = (
        "| [0001](0001-substrate-claude-code.md) | Substrate |\n"
        "Open items live in [`../DELAYED-DECISIONS.md`](../DELAYED-DECISIONS.md).\n"
        '[Spine]( ../specs/SPEC-spine.md "the policy spine" )\n'
        "[Section](../CHECKS.md#fast-lane)\n"
    )
    assert citations(text, base="docs/adr") == (
        Citation("path", "docs/adr/0001-substrate-claude-code.md", 1, False),
        Citation("path", "docs/DELAYED-DECISIONS.md", 2, False),
        Citation("path", "docs/specs/SPEC-spine.md", 3, False),
        Citation("anchor", "docs/CHECKS.md#fast-lane", 4, False),
    )


# --------------------------------------------------------------------------------------
# What is deliberately NOT a citation
# --------------------------------------------------------------------------------------


def test_external_urls_are_never_citations() -> None:
    text = (
        "Fetched from https://learn.chatgpt.com/docs/hooks and\n"
        "[the docs](https://example.com/a/b.md), [mail](mailto:x@example.com),\n"
        "[absolute](/etc/passwd), [fragment](#section), [outside](../../elsewhere.md),\n"
        "[self](.), [globbed](docs/adr/0043-*.md).\n"
    )
    assert citations(text) == ()


def test_git_refs_and_scheme_less_hosts_are_not_citations() -> None:
    text = "`git ls-tree origin/docs/handoff -- docs/adr/` and www.example.com/x/y.md\n"
    assert citations(text) == ()


def test_directories_globs_and_placeholders_are_not_citations() -> None:
    text = (
        "Records live under `docs/adr/`; the check files are `checks/NN_*.sh`;\n"
        "a module is `src/<pkg>/mod.py`; the prose range is `checks/00..50`;\n"
        "a globbed spec is `docs/specs/0043-*.md`.\n"
    )
    assert citations(text) == ()


def test_fenced_blocks_are_never_scanned() -> None:
    text = (
        "Real: `docs/CHECKS.md`.\n"
        "```toml\n"
        'required = ["00_build"]   # docs/NOWHERE.md\n'
        "```\n"
        "~~~\n"
        "`docs/ALSO-NOWHERE.md`\n"
        "~~~\n"
        "Back in prose: ADR-0043.\n"
    )
    assert citations(text) == (
        Citation("path", "docs/CHECKS.md", 1, False),
        Citation("adr", "ADR-0043", 8, False),
    )


def test_a_tilde_fence_does_not_close_a_backtick_fence() -> None:
    text = "```\n~~~\n`docs/NOWHERE.md`\n```\n`docs/CHECKS.md`\n"
    assert citations(text) == (Citation("path", "docs/CHECKS.md", 5, False),)


def test_a_link_written_inside_backticks_is_not_a_link() -> None:
    """It renders as literal text, so it cannot be a dead link — but a backticked *path*
    still is a citation, because that is how this repository writes its real ones."""
    text = "The form is `[text](target)`; the file is `docs/CHECKS.md`.\n"
    assert citations(text, base="docs/specs") == (Citation("path", "docs/CHECKS.md", 1, False),)


# --------------------------------------------------------------------------------------
# The forward-reference escape hatch
# --------------------------------------------------------------------------------------


def test_every_accepted_label_form() -> None:
    text = (
        "See `docs/PLUGIN.md` (lands with #166).\n"
        "See docs/PLUGIN.md (on feat/claude-plugin).\n"
        "See `docs/PLUGIN.md`, (Lands With `feat/claude-plugin`).\n"
        "See `docs/PLUGIN.md`; (ON #166).\n"
    )
    assert all(citation.has_forward_label for citation in citations(text))


def test_labels_that_are_not_labels() -> None:
    text = (
        "See `docs/PLUGIN.md` (on line 5).\n"
        "See `docs/PLUGIN.md` (soon).\n"
        "See `docs/PLUGIN.md` — it lands with #166 eventually.\n"
        "See `docs/PLUGIN.md` (lands with) #166.\n"
    )
    assert not any(citation.has_forward_label for citation in citations(text))


def test_labelled_citations_are_never_reported() -> None:
    found = citations("`docs/PLUGIN.md` (lands with #166) and `docs/GONE.md`.\n")
    assert unresolved(found, _resolver(set())) == (Citation("path", "docs/GONE.md", 1, False),)


# --------------------------------------------------------------------------------------
# Resolution and reporting
# --------------------------------------------------------------------------------------


def test_unresolved_keeps_source_order_and_drops_resolved() -> None:
    found = citations("`docs/CHECKS.md` `docs/GONE.md` `docs/ROADMAP.md` `docs/ALSO-GONE.md`\n")
    assert unresolved(found, _resolver({"docs/CHECKS.md", "docs/ROADMAP.md"})) == (
        Citation("path", "docs/GONE.md", 1, False),
        Citation("path", "docs/ALSO-GONE.md", 1, False),
    )


def test_render_names_file_line_and_citation() -> None:
    findings = [
        ("docs/4D-DRY-RUNS.md", Citation("path", "docs/HANDOFF.md", 205, False)),
        ("docs/SELF-ASSESSMENT.md", Citation("adr", "ADR-0057", 233, False)),
    ]
    assert render(findings) == (
        "UNRESOLVED CITATIONS — documentation on this branch cites what it does not contain:"
        "\n\n"
        "  docs/4D-DRY-RUNS.md:205 — docs/HANDOFF.md — does not exist on this branch\n"
        "  docs/SELF-ASSESSMENT.md:233 — ADR-0057 — does not exist on this branch\n"
        "\n"
        "Fix the document. If the reference is deliberately ahead of this branch, label it "
        "in place: `docs/THING.md` (lands with #NNN). See docs/specs/SPEC-citations.md."
    )


def test_render_with_no_findings_still_renders_its_frame() -> None:
    assert render(()).splitlines()[0].startswith("UNRESOLVED CITATIONS")


# --------------------------------------------------------------------------------------
# Anchors, headings and the small pure helpers
# --------------------------------------------------------------------------------------


def test_heading_slugs_follow_the_github_shape_and_skip_fences() -> None:
    text = (
        "# borromeanRings — Checks Catalog\n"
        "## Enabling checks in a project\n"
        "### 1. What counts as a citation (and nothing else does)\n"
        "####### not a heading\n"
        "```bash\n"
        "# not a heading either\n"
        "```\n"
        "## Closed heading ##\n"
    )
    assert heading_slugs(text) == (
        "borromeanrings--checks-catalog",
        "enabling-checks-in-a-project",
        "1-what-counts-as-a-citation-and-nothing-else-does",
        "closed-heading",
    )


def test_slugify_exact_values() -> None:
    assert slugify("  Fast lane — shared checks (language-agnostic) ") == (
        "fast-lane--shared-checks-language-agnostic"
    )
    assert slugify("`emit_noop` & friends") == "emit_noop--friends"


def test_prose_lines_numbers_from_one_and_skips_fenced_content() -> None:
    assert list(prose_lines("a\n```\nb\n```\nc\n")) == [(1, "a"), (5, "c")]


def test_code_spans_pairs_runs_of_equal_width() -> None:
    assert code_spans("no backticks here") == []
    assert code_spans("a `b` c ``d`` e") == [(2, 5), (8, 13)]
    assert code_spans("unclosed `span") == []
    # A run of a different width in between is skipped, not mistaken for the closer.
    assert code_spans("`a ``b`` c`") == [(0, 11)]
