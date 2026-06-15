"""Tests for the Phase-1 deep-research core (docs/SPEC-deep-research.md §5).

Verification = deterministic retrieval + an injected semantic judge. The 1925
regression test encodes the lesson from live testing: lexical overlap alone
false-positives, so the judge (agent/LLM) must decide entailment.
"""

from meta_harness.deep_research import (
    Source,
    candidate_passages,
    research,
    verify_claim,
)

_SOURCES = (
    Source(
        url="https://example.org/eiffel",
        title="Eiffel Tower",
        text=(
            "The Eiffel Tower was completed in 1889. "
            "In 1925, a con artist sold the tower for scrap."
        ),
    ),
)


def _judge(claim: str, passage: str) -> bool:
    """A stand-in semantic judge: a year-claim holds only if the passage says the
    structure was *completed* in that exact year (not merely mentions the year)."""
    years = [tok for tok in claim.split() if tok.isdigit()]
    return "completed" in passage.lower() and all(y in passage for y in years)


def test_candidate_passages_ranks_by_overlap() -> None:
    candidates = candidate_passages("Eiffel Tower completed 1889", _SOURCES)
    assert candidates[0][0] == "https://example.org/eiffel"
    assert "1889" in candidates[0][1]


def test_verify_supported_when_judge_agrees() -> None:
    verdict = verify_claim("Eiffel Tower completed 1889", _SOURCES, _judge)
    assert verdict.supported is True
    assert "1889" in verdict.passage


def test_verify_rejects_fabricated_year_even_if_year_appears_elsewhere() -> None:
    # "1925" appears in the source (the scam), but not as a completion date →
    # the semantic judge rejects it. Lexical overlap alone would wrongly accept.
    verdict = verify_claim("Eiffel Tower completed 1925", _SOURCES, _judge)
    assert verdict.supported is False
    assert verdict.source_url == ""


def test_verify_no_candidates_is_unsupported() -> None:
    assert verify_claim("the of in", _SOURCES, _judge).supported is False


def test_research_dedupes_and_records_trail() -> None:
    results = [("u1", "A"), ("u1", "A"), ("u2", "B")]
    report = research("q", lambda _q: results, lambda u: f"text for {u}")
    assert [s.url for s in report.sources] == ["u1", "u2"]
    assert report.trail[0] == "search: 'q'"
    assert any("skip duplicate" in step for step in report.trail)


def test_research_respects_max_sources() -> None:
    results = [("u1", "A"), ("u2", "B"), ("u3", "C")]
    report = research("q", lambda _q: results, lambda _u: "x", max_sources=2)
    assert len(report.sources) == 2
