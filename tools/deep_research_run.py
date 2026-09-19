"""End-to-end runner for borromeanRings's deep-research enhancement (real web sources).

Usage:
    python tools/deep_research_run.py "<query>" ["<claim>" ...]

Ties the whole enhancement together on real sources and STREAMS THE ACTUAL SEARCH
ACTIVITY: every query sent, every literal request URL hit, every source read.

What it really does today: HTTP calls to the **Wikipedia API** (en + simple) — not
a browser, and not a general web search engine. That was the reliable, keyless way
to prove the pipeline; real search engines / a real browser are a future swap
behind the same SearchFn/FetchFn adapters.

The semantic steps (query mutation, gap-finding, entailment judging) are performed
by the wrapped agent / an LLM in a real borromeanRings session; this standalone runner
uses honest deterministic STAND-INS so it runs without an API key.
"""

import json
import re
import sys
import urllib.parse
import urllib.request

from meta_harness.deep_research import (
    ResearchEvent,
    enhanced_research,
    federated_search,
    render_event,
    render_report,
    report_findings,
)

_UA = "borromeanrings-deep-research/0.0 (https://github.com/Elmdin/borromeanrings)"
_ENGINES = ("en.wikipedia.org", "simple.wikipedia.org")


def _get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (trusted host)
        return json.load(response)


def _api_url(host: str, params: dict[str, str]) -> str:
    return f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)


def _engine(host: str, emit):
    def search(query: str) -> list[tuple[str, str]]:
        url = _api_url(
            host,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": "4",
                "format": "json",
            },
        )
        emit(ResearchEvent("request", f"GET {url}"))  # the literal search request
        data = _get(url)
        return [
            (f"https://{host}/wiki/{urllib.parse.quote(h['title'])}", h["title"])
            for h in data["query"]["search"]
        ]

    return search


def _fetcher(emit):
    def fetch(url: str) -> str:
        parts = url.split("/")
        host, title = parts[2], urllib.parse.unquote(parts[-1])
        req = _api_url(
            host,
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": "1",
                "titles": title,
                "format": "json",
            },
        )
        emit(ResearchEvent("request", f"GET {req}"))  # the literal fetch request
        data = _get(req)
        return next(iter(data["query"]["pages"].values())).get("extract", "")

    return fetch


# --- deterministic stand-ins for the wrapped agent's semantic steps -----------
def mutator(query: str) -> list[str]:  # real: agent's DMQR / pseudo-answer
    return [f"{query} history", f"{query} facts"]


_gap_calls = {"n": 0}


def gap_finder(query: str, _sources: object) -> list[str]:  # real: agent proposes angles
    _gap_calls["n"] += 1
    return [f"{query} construction"] if _gap_calls["n"] == 1 else []


def judge(claim: str, passage: str) -> bool:  # real: agent's entailment judgment
    distinctive = {t for t in re.findall(r"[a-z0-9]+", claim.lower()) if t.isdigit() or len(t) >= 5}
    passage_lower = passage.lower()
    return bool(distinctive) and all(token in passage_lower for token in distinctive)


def main() -> None:
    query = sys.argv[1]
    claims = sys.argv[2:]

    def emit(event: ResearchEvent) -> None:
        print("  " + render_event(event), flush=True)

    engines = [_engine(host, emit) for host in _ENGINES]

    def federated(q: str) -> list[tuple[str, str]]:
        return federated_search(q, engines)

    print("LIVE TRAIL (queries sent · request URLs · sources read · rounds):")
    report = enhanced_research(
        query,
        federated,
        _fetcher(emit),
        gap_finder,
        mutator=mutator,
        dry_rounds=2,
        max_sources=8,
        on_event=emit,
    )
    print(f"\nSOURCES GATHERED ({len(report.sources)}):")
    for source in report.sources:
        print(f"  - {source.title}")

    if claims:
        cited = report_findings(query, claims, report.sources, [judge, judge, judge], min_agree=2)
        print("\n" + render_report(cited))
    print(
        "\n(Wikipedia-API HTTP calls, not a browser. LLM steps are stand-ins; "
        "the agent is the real judge.)"
    )


if __name__ == "__main__":
    main()
