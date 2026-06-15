"""Live runner for the Phase-1 deep-research slice (real sources via Wikipedia).

Usage: python tools/deep_research_demo.py "<query>" "<claim>"

This is the runnable demo: it really searches and fetches, then verifies the
claim against the fetched text. Wikipedia is the Phase-1 search/fetch adapter
(one engine; federated multi-engine is Phase 2). Not part of the gated package
(it lives outside src), so network code stays out of the tested core.
"""

import json
import sys
import urllib.parse
import urllib.request

from meta_harness.deep_research import candidate_passages, research

_API = "https://en.wikipedia.org/w/api.php"


_UA = "borromeo-deep-research/0.0 (https://github.com/Elmdin/borromeo)"


def _api(params: dict[str, str]) -> dict:
    url = _API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (trusted host)
        return json.load(response)


def search_fn(query: str) -> list[tuple[str, str]]:
    data = _api(
        {"action": "query", "list": "search", "srsearch": query, "srlimit": "5", "format": "json"}
    )
    results = []
    for hit in data["query"]["search"]:
        title = hit["title"]
        results.append((f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}", title))
    return results


def fetch_fn(url: str) -> str:
    title = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    data = _api(
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": "1",
            "titles": title,
            "format": "json",
        }
    )
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    return page.get("extract", "")


def main() -> None:
    query, claim = sys.argv[1], sys.argv[2]
    report = research(query, search_fn, fetch_fn, max_sources=3)

    print("TRAIL (what borromeo did, step by step):")
    for step in report.trail:
        print(f"  - {step}")
    print(f"\nSOURCES READ ({len(report.sources)}):")
    for source in report.sources:
        print(f"  - {source.title}  ({len(source.text)} chars)")

    print(f'\nCLAIM: "{claim}"')
    print("Top candidate passages (deterministic retrieval from the fetched text):")
    candidates = candidate_passages(claim, report.sources, k=3)
    if not candidates:
        print("  (none — nothing in the fetched sources bears on this claim)")
    for url, passage in candidates:
        print(f"  • {url}\n    {passage[:240]}")
    print(
        "\nVERDICT: the semantic entailment check (does a passage actually support the claim?) "
        "is performed by the wrapped agent / an LLM — borromeo structures and enforces it. "
        "Lexical retrieval only narrows; it never decides truth."
    )


if __name__ == "__main__":
    main()
