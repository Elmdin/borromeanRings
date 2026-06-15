"""Tests for the Phase-1 deep-research core (docs/SPEC-deep-research.md §5).

Verification = deterministic retrieval + an injected semantic judge. The 1925
regression test encodes the lesson from live testing: lexical overlap alone
false-positives, so the judge (agent/LLM) must decide entailment.
"""

from meta_harness.deep_research import (
    Source,
    candidate_passages,
    federated_search,
    make_entailment_judge,
    multi_query_search,
    mutate_queries,
    research,
    verify_claim,
    verify_claim_adversarial,
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


def test_adversarial_supported_when_enough_judges_agree() -> None:
    yes, no = (lambda _c, _p: True), (lambda _c, _p: False)
    verdict = verify_claim_adversarial(
        "Eiffel Tower completed 1889", _SOURCES, [yes, yes, no], min_agree=2
    )
    assert verdict.supported is True
    assert verdict.votes == (True, True, False)


def test_adversarial_rejects_when_too_few_agree_fail_closed() -> None:
    yes, no = (lambda _c, _p: True), (lambda _c, _p: False)
    verdict = verify_claim_adversarial(
        "Eiffel Tower completed 1889", _SOURCES, [yes, no, no], min_agree=2
    )
    assert verdict.supported is False
    assert verdict.source_url == ""


def test_entailment_judge_is_fail_closed() -> None:
    # Only an explicit "yes" passes; "unsure"/anything else is rejected.
    judge = make_entailment_judge(lambda prompt: "yes" if "1889" in prompt else "I'm not sure")
    assert judge("completed 1889", "completed in 1889") is True
    assert judge("completed 1925", "sold for scrap") is False


def test_federated_search_fuses_and_dedupes_by_rank() -> None:
    def engine_a(_q: str) -> list[tuple[str, str]]:
        return [("u1", "A1"), ("shared", "A2"), ("u3", "A3")]  # longer engine

    def engine_b(_q: str) -> list[tuple[str, str]]:
        return [("u2", "B1"), ("shared", "B2")]  # shorter → exercises rank >= len branch

    merged = federated_search("q", [engine_a, engine_b])
    # rank0: u1,u2 · rank1: shared(A2), B's shared dup→skip · rank2: u3 (B exhausted)
    assert merged == [("u1", "A1"), ("u2", "B1"), ("shared", "A2"), ("u3", "A3")]


def test_federated_search_empty() -> None:
    assert federated_search("q", []) == []


def test_mutate_queries_keeps_original_dedupes_and_caps() -> None:
    def mutator(q: str) -> list[str]:
        return [q, "Q", "", "q2", "q3", "q4", "q5"]  # dup of original, empty, then variants

    out = mutate_queries("q", mutator, max_variants=3)
    assert out[0] == "q"  # original always first, never lost
    assert out == ["q", "q2", "q3"]  # "Q" dedup (case-insensitive), "" skipped, capped at 3


def test_multi_query_search_fans_out_and_fuses() -> None:
    def mutator(_q: str) -> list[str]:
        return ["broad"]

    def search_fn(q: str) -> list[tuple[str, str]]:
        return [("orig-hit", q)] if q == "q" else [("broad-hit", q)]

    merged = multi_query_search("q", mutator, search_fn)
    assert {url for url, _ in merged} == {"orig-hit", "broad-hit"}  # both queries' sources


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
