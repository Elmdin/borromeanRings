"""Deep Research — Phase 1 vertical slice (Layer 2).

A thin, end-to-end, runnable pipeline: search a query, fetch real sources, and
**verify a claim against the actually-fetched source text** (not the model's
memory) — borromeo's anti-hallucination differentiator. Search and fetch are
injected adapters (substrate-agnostic and testable); the run records a visible
trail.

v1 verification is deterministic and lexical: a claim is *supported* only if
every content word of the claim appears in a source's fetched text — so a claim
with a fabricated specific (a wrong year, a made-up name) is **rejected** because
that term is absent. Semantic/NLI verification is a later phase (see
docs/SPEC-deep-research.md). This is honest about its limits, by design.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

# Search adapter: query -> list of (url, title). Fetch adapter: url -> plain text.
SearchFn = Callable[[str], Sequence[tuple[str, str]]]
FetchFn = Callable[[str], str]

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "was",
        "were",
        "are",
        "has",
        "have",
        "had",
        "with",
        "that",
        "this",
        "from",
        "its",
        "it",
        "in",
        "on",
        "at",
        "to",
        "of",
        "as",
        "by",
        "an",
        "is",
        "be",
        "or",
        "a",
    }
)


@dataclass(frozen=True)
class Source:
    """A fetched source: where it came from and its text."""

    url: str
    title: str
    text: str


@dataclass(frozen=True)
class Verdict:
    """The result of verifying a claim against fetched sources.

    ``votes`` records each adversarial judge's call (auditable in the receipt).
    """

    supported: bool
    source_url: str
    passage: str
    votes: tuple[bool, ...] = ()


@dataclass(frozen=True)
class Report:
    """The outcome of a research run: the sources read and the visible trail."""

    query: str
    sources: tuple[Source, ...]
    trail: tuple[str, ...]


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


# Entailment judge: (claim, passage) -> does the passage actually support the claim?
# Performed by the wrapped agent / an LLM (borromeo enforces + structures it); injected
# so the deterministic parts stay testable. Lexical overlap is NOT a judge — testing
# showed it false-positives (a fabricated "1925" matched an unrelated 1925 mention).
Judge = Callable[[str, str], bool]


def candidate_passages(claim: str, sources: Sequence[Source], k: int = 3) -> list[tuple[str, str]]:
    """Deterministic retrieval: narrow sources to the top-k passages most likely
    to bear on the claim (by content-word overlap). This only *narrows*; it does
    not decide truth. Returns (source_url, passage) best-first.
    """
    needed = _content_words(claim)
    scored: list[tuple[int, str, str]] = []
    for source in sources:
        for sentence in _sentences(source.text):
            overlap = len(needed & _content_words(sentence))
            if overlap:
                scored.append((overlap, source.url, sentence))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [(url, passage) for _score, url, passage in scored[:k]]


def verify_claim(claim: str, sources: Sequence[Source], judge: Judge) -> Verdict:
    """Verify a claim against fetched sources: retrieve candidate passages, then
    ask the injected *judge* whether a passage actually entails the claim.

    Fail-closed: if no candidate is judged to support the claim, it is rejected
    (not hallucinated). The judge is the semantic step (agent/LLM); retrieval is
    deterministic.
    """
    for url, passage in candidate_passages(claim, sources):
        if judge(claim, passage):
            return Verdict(supported=True, source_url=url, passage=passage, votes=(True,))
    return Verdict(supported=False, source_url="", passage="")


def verify_claim_adversarial(
    claim: str, sources: Sequence[Source], judges: Sequence[Judge], *, min_agree: int
) -> Verdict:
    """Adversarial, fail-closed verification: a claim is supported only if at least
    ``min_agree`` of the (independent, skeptical) judges affirm entailment for the
    *same* candidate passage. No qualifying passage ⇒ rejected. More judges that
    must agree = stricter. The judges are the semantic step (agent/LLM); borromeo
    structures the panel and records the votes.
    """
    for url, passage in candidate_passages(claim, sources):
        votes = tuple(judge(claim, passage) for judge in judges)
        if sum(votes) >= min_agree:
            return Verdict(supported=True, source_url=url, passage=passage, votes=votes)
    return Verdict(supported=False, source_url="", passage="")


def make_entailment_judge(ask: Callable[[str], str]) -> Judge:
    """Build a skeptical entailment judge from an LLM/agent ``ask(prompt) -> answer``.

    This is how the wrapped agent or an API performs the judgment. Fail-closed:
    only an explicit affirmative counts; anything else (incl. "unsure") is a no.
    """

    def judge(claim: str, passage: str) -> bool:
        prompt = (
            "You are a strict fact-checker. Does the PASSAGE explicitly support the "
            "CLAIM (not merely share words or mention the topic)? Reply 'yes' or 'no'; "
            f"if unsure, reply 'no'.\nCLAIM: {claim}\nPASSAGE: {passage}\nAnswer:"
        )
        return ask(prompt).strip().lower().startswith("y")

    return judge


# Query mutator: query -> diverse variants that widen recall. Generated by the
# wrapped agent/LLM (DMQR / pseudo-answer); borromeo structures the result.
QueryMutator = Callable[[str], Sequence[str]]


def _fuse(result_lists: Sequence[Sequence[tuple[str, str]]]) -> list[tuple[str, str]]:
    """Round-robin fuse ranked result lists, deduping by URL (rank-0 of each list,
    then rank-1 of each, …). Shared by multi-engine and multi-query fan-out."""
    seen: set[str] = set()
    merged: list[tuple[str, str]] = []
    for rank in range(max((len(results) for results in result_lists), default=0)):
        for results in result_lists:
            if rank < len(results):
                url, title = results[rank]
                if url not in seen:
                    seen.add(url)
                    merged.append((url, title))
    return merged


def federated_search(query: str, search_fns: Sequence[SearchFn]) -> list[tuple[str, str]]:
    """Run several search backends and fuse their results — no single engine is
    authoritative. Broader coverage than any one engine. Drop-in `SearchFn` body:
    ``lambda q: federated_search(q, [engine_a, engine_b])``.
    """
    return _fuse([list(search_fn(query)) for search_fn in search_fns])


def mutate_queries(query: str, mutator: QueryMutator, max_variants: int = 5) -> list[str]:
    """Widen recall: the user's original query (**never dropped**) plus deduped,
    diverse variants from the mutator (the agent/LLM). borromeo enforces: original
    kept first, deduped (case-insensitive), capped at ``max_variants``.
    """
    out = [query]
    seen = {query.strip().lower()}
    for variant in mutator(query):
        key = variant.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(variant)
        if len(out) >= max_variants:
            break
    return out


def multi_query_search(
    query: str, mutator: QueryMutator, search_fn: SearchFn, max_variants: int = 5
) -> list[tuple[str, str]]:
    """Fan a search across the original + mutated queries and fuse the results —
    so a weak/narrow query still reaches sources the variants surface."""
    queries = mutate_queries(query, mutator, max_variants)
    return _fuse([list(search_fn(variant)) for variant in queries])


def research(query: str, search_fn: SearchFn, fetch_fn: FetchFn, max_sources: int = 5) -> Report:
    """Run the Phase-1 pipeline: search → dedup → fetch, recording a trail."""
    trail: list[str] = [f"search: {query!r}"]
    seen: set[str] = set()
    sources: list[Source] = []
    for url, title in search_fn(query):
        if url in seen:
            trail.append(f"skip duplicate: {url}")
            continue
        seen.add(url)
        text = fetch_fn(url)
        trail.append(f"chose + read {len(text)} chars: {url}")
        sources.append(Source(url=url, title=title, text=text))
        if len(sources) >= max_sources:
            break
    return Report(query=query, sources=tuple(sources), trail=tuple(trail))


# Gap-finder: (original query, sources found so far) -> more queries / angles to try.
# The completeness critic's semantic step — the agent/LLM proposes where ELSE to look
# (a weak query, the wrong place, a barely-missed detail). borromeo runs the loop.
GapFinder = Callable[[str, Sequence[Source]], Sequence[str]]


@dataclass(frozen=True)
class ResearchEvent:
    """A step the research process emits live, so the user can watch it work."""

    step: str  # "source" | "round" | "saturated" | "max_sources"
    detail: str


# An event sink receives events as they happen (e.g. print them for a live view).
EventSink = Callable[[ResearchEvent], None]


def _emit(sink: EventSink | None, step: str, detail: str) -> None:
    if sink is not None:
        sink(ResearchEvent(step=step, detail=detail))


def render_event(event: ResearchEvent) -> str:
    """Format an event for a live CLI view."""
    return f"[{event.step}] {event.detail}"


def research_until_saturated(
    query: str,
    search_fn: SearchFn,
    fetch_fn: FetchFn,
    gap_finder: GapFinder,
    *,
    dry_rounds: int = 2,
    max_rounds: int = 6,
    max_sources: int = 20,
    on_event: EventSink | None = None,
) -> Report:
    """The completeness critic ("don't miss anything"): research, then keep asking
    the gap-finder for unexplored angles and researching those, until coverage
    **saturates** — ``dry_rounds`` consecutive rounds that add no new source. Always
    bounded by ``max_rounds`` and ``max_sources`` (never an unbounded loop). The
    gap-finder is the agent/LLM; borromeo runs the loop and decides saturation.
    """
    seen: set[str] = set()
    sources: list[Source] = []
    trail: list[str] = []
    queries: list[str] = [query]
    dry = 0
    for round_no in range(1, max_rounds + 1):
        added = 0
        for variant in queries:
            _emit(on_event, "query", f"searching {variant!r}")
            for url, title in search_fn(variant):
                if url not in seen and len(sources) < max_sources:
                    seen.add(url)
                    text = fetch_fn(url)
                    sources.append(Source(url=url, title=title, text=text))
                    added += 1
                    _emit(on_event, "source", f"{title} <- {url} ({len(text)} chars)")
        summary = f"round {round_no}: {len(queries)} queries -> +{added} new (total {len(sources)})"
        trail.append(summary)
        _emit(on_event, "round", summary)
        dry = dry + 1 if added == 0 else 0
        if dry >= dry_rounds:
            done = f"saturated: {dry} dry round(s) added nothing new -- stopping"
            trail.append(done)
            _emit(on_event, "saturated", done)
            break
        if len(sources) >= max_sources:
            done = f"hit max_sources={max_sources} -- stopping"
            trail.append(done)
            _emit(on_event, "max_sources", done)
            break
        queries = [q for q in gap_finder(query, tuple(sources)) if q.strip()]
    return Report(query=query, sources=tuple(sources), trail=tuple(trail))


@dataclass(frozen=True)
class CitedReport:
    """A synthesized answer: only verified claims, each with its citation."""

    query: str
    statements: tuple[tuple[str, str], ...]  # (verified claim, source_url)
    rejected: tuple[str, ...]  # claims dropped because unverified


def synthesize(query: str, findings: Sequence[tuple[str, Verdict]]) -> CitedReport:
    """The deterministic output gate: assemble a report from claim→Verdict findings,
    admitting **only** verified claims (each with its source). Unverified claims are
    dropped into ``rejected`` — they never appear as stated facts (fail-closed). The
    prose may be elaborated by the agent later; what borromeo guarantees is that no
    unverified claim survives into the output.
    """
    statements = tuple(
        (claim, verdict.source_url) for claim, verdict in findings if verdict.supported
    )
    rejected = tuple(claim for claim, verdict in findings if not verdict.supported)
    return CitedReport(query=query, statements=statements, rejected=rejected)


def render_report(report: CitedReport) -> str:
    """Render a CitedReport as human-readable, fully-cited text."""
    lines = [f"# {report.query}", ""]
    for claim, url in report.statements:
        lines.append(f"- {claim}  [source: {url}]")
    if report.rejected:
        lines.append("")
        lines.append("Rejected (unverified — deliberately not stated):")
        lines.extend(f"- {claim}" for claim in report.rejected)
    return "\n".join(lines)


def report_findings(
    query: str,
    claims: Sequence[str],
    sources: Sequence[Source],
    judges: Sequence[Judge],
    *,
    min_agree: int,
) -> CitedReport:
    """End-to-end gated reporting: adversarially verify each claim against the
    sources, then synthesize a report containing only the verified ones."""
    findings = [
        (claim, verify_claim_adversarial(claim, sources, judges, min_agree=min_agree))
        for claim in claims
    ]
    return synthesize(query, findings)


def enhanced_research(
    query: str,
    agent_search_fn: SearchFn,
    fetch_fn: FetchFn,
    gap_finder: GapFinder,
    *,
    mutator: QueryMutator | None = None,
    dry_rounds: int = 2,
    max_rounds: int = 6,
    max_sources: int = 20,
    on_event: EventSink | None = None,
) -> Report:
    """Augment the wrapped agent's *own* research (don't replace it).

    The agent's search (``agent_search_fn``) is the base; borromeo *enhances* it:
    optionally widens each query (query mutation), runs the completeness loop until
    coverage saturates, and streams live events. Verification + gated synthesis are
    applied to extracted claims via :func:`report_findings`. Everything is injected
    (search, fetch, mutator, gap-finder, judges), so it works with any agent, engine,
    or bare LLM — borromeo enhances, the agent performs.
    """

    def search_fn(q: str) -> Sequence[tuple[str, str]]:
        if mutator is None:
            return agent_search_fn(q)
        return multi_query_search(q, mutator, agent_search_fn)

    return research_until_saturated(
        query,
        search_fn,
        fetch_fn,
        gap_finder,
        dry_rounds=dry_rounds,
        max_rounds=max_rounds,
        max_sources=max_sources,
        on_event=on_event,
    )
