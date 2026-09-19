"""Prior-art gate: did anyone look before building this?

The maintainer's own workflow rules mandate a research-and-reuse step before any new
implementation. Nothing enforced it, so every agent, every session, had to be reminded —
and still wrote its own hash function instead of using the one the repo already had.

This is the ``13_adr`` pattern (ADR-0043) applied to reuse: on a feature branch, a change
that **adds public surface** must also add or modify a *survey record* under
``docs/surveys/`` — a short note of what already existed (in the repo, in a declared
dependency, in the ecosystem) and why building was still the right call. What the gate
demands is that the question was *asked and answered on the record*; it does not judge
the answer.

Two deliberate limits (see ADR-0051 and ``docs/research/AGENT-TOOLING-SURVEY.md``):

* "Is there already a library for this?" is **not** gated. No key-free package API
  supports free-text search (deps.dev, ecosyste.ms, PyPI and libraries.io were all
  probed), so a gate could not answer its own question deterministically — the exact
  hollow-green failure ``01_source_coherence`` exists to prevent. That half is advisory.
* In-repo *reimplementation* signals come from Ruff's ``reimplemented-*`` rules enabled
  in ``20_lint`` — the only shipping rules of their kind — not from anything here.

Pure decision core, no I/O: the check gathers sources and paths; this decides.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from meta_harness.api_diff import public_api


def _names(source: str) -> set[str]:
    """Public top-level symbol names in ``source``; empty when it does not parse.

    Top-level only, as ADR-0051 states: ``public_api`` also lists methods (dotted
    ``Class.method``), but adding a method to an existing class is elaboration of a
    surface that already exists, not new surface that warrants a prior-art survey.
    """
    try:
        return {name for name in public_api(source) if "." not in name}
    except SyntaxError:
        return set()


def new_public_symbols(old: Mapping[str, str], new: Mapping[str, str]) -> dict[str, list[str]]:
    """Public symbols present in ``new`` but absent from ``old``, keyed by path.

    ``old``/``new`` map a path to its source at the merge-base and at HEAD; a path
    missing from ``old`` is a brand-new file, so every public symbol in it is new.
    Removals are not reported — this gate is about what was *added* without looking.
    Unparseable source contributes nothing rather than failing: syntax is ``20_lint``'s
    job, and a crash here would fail the gate for the wrong reason.
    """
    added: dict[str, list[str]] = {}
    for path, source in new.items():
        fresh = sorted(_names(source) - _names(old.get(path, "")))
        if fresh:
            added[path] = fresh
    return added


def survey_violation(
    branch: str,
    new_symbols: Mapping[str, Sequence[str]],
    changed_paths: Sequence[str],
    *,
    survey_dir: str = "docs/surveys",
    require_prefixes: Sequence[str] = ("feat/",),
) -> str | None:
    """Reason this change adds public surface without a survey record, else ``None``.

    Only feature branches are held to it. A change that adds nothing public has nothing
    to survey and returns ``None`` — the caller reports that honestly as ``noop``, since
    the gate inspected the diff and found no question to ask (ADR-0049). Prefix matching
    is boundary-safe: ``docs/surveys_old/`` does not satisfy ``docs/surveys/``.
    """
    if not any(branch.startswith(prefix) for prefix in require_prefixes):
        return None
    if not new_symbols:
        return None
    prefix = survey_dir.rstrip("/") + "/"
    if any(path.startswith(prefix) for path in changed_paths):
        return None
    listing = "; ".join(
        f"{path}: {', '.join(names)}" for path, names in sorted(new_symbols.items())
    )
    return (
        f"feature branch '{branch}' adds public surface with no survey of what already "
        f"exists — {listing}. Record what you found (in this repo, in a dependency, in the "
        f"ecosystem) and why building was still right, under {survey_dir}/ "
        f"(see {survey_dir}/TEMPLATE.md)."
    )
