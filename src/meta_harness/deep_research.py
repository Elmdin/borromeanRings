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
