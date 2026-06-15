"""End-to-end runner for borromeo's deep-research enhancement (real web sources).

Usage:
    python tools/deep_research_run.py "<query>" ["<claim>" ...]

Ties the whole enhancement together on real Wikipedia sources:
  federated multi-engine search + query mutation + completeness loop (live trail)
  -> for each claim: adversarial citation verification -> gated cited report.

The semantic steps (query mutation, gap-finding, entailment judging) are
performed by the wrapped agent / an LLM in a real borromeo session. This runner
has no API key, so it uses **honest deterministic stand-ins** for those steps —
clearly marked — so the pipeline runs autonomously and you can see it work.
"""

import json
import re
import sys
import urllib.parse
import urllib.request

from meta_harness.deep_research import (
    enhanced_research,
    federated_search,
    render_event,
    render_report,
    report_findings,
)

_UA = "borromeo-deep-research/0.0 (https://github.com/Elmdin/borromeo)"
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
                "srlimit": "4",
                "format": "json",
            },
        )
        return [
            (f"https://{host}/wiki/{urllib.parse.quote(h['title'])}", h["title"])
            for h in data["query"]["search"]
        ]

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
    return next(iter(data["query"]["pages"].values())).get("extract", "")


def federated(query: str) -> list[tuple[str, str]]:
    return federated_search(query, [_engine(host) for host in _ENGINES])


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

    print("LIVE TRAIL (federated multi-engine + query mutation + completeness loop):")
    report = enhanced_research(
        query,
        federated,
        fetch_fn,
        gap_finder,
        mutator=mutator,
        dry_rounds=2,
        max_sources=8,
        on_event=lambda event: print("  " + render_event(event), flush=True),
    )
    print(f"\nSOURCES GATHERED ({len(report.sources)}):")
    for source in report.sources:
        print(f"  - {source.title}")

    if claims:
        cited = report_findings(query, claims, report.sources, [judge, judge, judge], min_agree=2)
        print("\n" + render_report(cited))
    print(
        "\n(LLM steps used deterministic stand-ins; the wrapped agent is the real judge/mutator.)"
    )


if __name__ == "__main__":
    main()
