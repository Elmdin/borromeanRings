"""Live runner for the deep-research enhancement (real sources via Wikipedia).

Usage: python tools/deep_research_demo.py "<query>" "<claim>"

It really searches and fetches, then surfaces candidate passages for the claim.
Two engines are federated (English + Simple Wikipedia) to show multi-engine
coverage; real search engines plug in via the same SearchFn adapter. The semantic
verdict is performed by the wrapped agent / an LLM (borromeanRings structures it). Lives
outside src, so network code stays out of the tested core.
"""

import json
import sys
import urllib.parse
import urllib.request

from meta_harness.deep_research import candidate_passages, federated_search, research

_UA = "borromeanrings-deep-research/0.0 (https://github.com/Elmdin/borromeanrings)"
_ENGINES = ("en.wikipedia.org", "simple.wikipedia.org")


def _api(host: str, params: dict[str, str]) -> dict:
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 (trusted host)
        return json.load(response)


def _engine(host: str):
    def search(query: str) -> list[tuple[str, str]]:
        data = _api(
            host,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": "5",
                "format": "json",
            },
        )
        out = []
        for hit in data["query"]["search"]:
            title = hit["title"]
            out.append((f"https://{host}/wiki/{urllib.parse.quote(title)}", title))
        return out

    return search


def fetch_fn(url: str) -> str:
    parts = url.split("/")
    host, title = parts[2], urllib.parse.unquote(parts[-1])
    data = _api(
        host,
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": "1",
            "titles": title,
            "format": "json",
        },
    )
    page = next(iter(data["query"]["pages"].values()))
    return page.get("extract", "")


def main() -> None:
    query, claim = sys.argv[1], sys.argv[2]
    engines = [_engine(host) for host in _ENGINES]
    report = research(query, lambda q: federated_search(q, engines), fetch_fn, max_sources=4)

    print(f"ENGINES FEDERATED: {', '.join(_ENGINES)}")
    print("TRAIL (step by step):")
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
        "\nVERDICT: semantic entailment (does a passage actually support the claim?) "
        "is performed by the wrapped agent / an LLM via verify_claim_adversarial — "
        "borromeanRings structures + records it, fail-closed. Lexical retrieval only narrows."
    )


if __name__ == "__main__":
    main()
