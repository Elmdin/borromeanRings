"""Container (Dockerfile) hygiene: the operational invariants no code check covers.

A service shipped as a container carries invariants the source tree can't express:
it should run as a **non-root** user (least privilege), **pin its base image**
(reproducible builds — ``:latest`` drifts under you), and — for a long-running
service — declare a **HEALTHCHECK** so an orchestrator can tell live from wedged.
This is the buildable, deterministic slice of matrix #4 (SRE / operational): each
rule is a yes/no fact derivable from the Dockerfile text, no arbitrary threshold.

Pure parsing here (stdlib only; no docker/hadolint dependency) — the check script
supplies the Dockerfile text and the rule set to enforce. Which rules apply is the
governed project's call: a gate-runner that runs-and-exits has no liveness to probe,
so it omits ``healthcheck``; a service keeps all three. See
docs/specs/SPEC-container.md and ADR-0044.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: Every hygiene rule this module knows. The default enforced set (see
#: ``spine.load_config``) is all three; a project narrows it via ``[container].require``.
ALL_RULES: tuple[str, ...] = ("non_root", "pinned_base", "healthcheck")

#: Base images that are their own pin — ``scratch`` is the empty base (no tag to
#: drift). Kept as a set so ``FROM scratch`` never trips the pinned-base rule.
_SELF_PINNED_BASES = frozenset({"scratch"})


@dataclass(frozen=True)
class ContainerFinding:
    """A single hygiene violation: which rule failed and a human-facing reason."""

    rule: str
    message: str


def _logical_lines(dockerfile: str) -> list[str]:
    """Collapse a Dockerfile to its instruction lines.

    Joins backslash line-continuations, drops blank lines and ``#`` parser/comment
    lines (a comment line is skipped even mid-continuation, as Docker does). Each
    returned string is one logical instruction (``FROM ...``, ``USER ...``).
    """
    lines: list[str] = []
    buffer = ""
    for raw in dockerfile.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue  # parser directive / comment — not part of any instruction
        if stripped.endswith("\\"):
            buffer += stripped[:-1].rstrip() + " "
            continue
        buffer += stripped
        lines.append(buffer.strip())
        buffer = ""
    if buffer.strip():
        lines.append(buffer.strip())
    return [line for line in lines if line]  # drop blanks; no empty instruction lines


def _split_instruction(line: str) -> tuple[str, str]:
    """Return ``(OP, rest)`` for an instruction line; OP upper-cased for matching."""
    parts = line.split(None, 1)
    return parts[0].upper(), (parts[1].strip() if len(parts) > 1 else "")


def _from_image_and_alias(rest: str) -> tuple[str, str | None]:
    """Parse a ``FROM`` argument into ``(image_ref, stage_alias | None)``."""
    tokens = rest.split()
    if not tokens:
        return "", None
    image = tokens[0]
    alias: str | None = None
    for i, token in enumerate(tokens):
        if token.upper() == "AS" and i + 1 < len(tokens):
            alias = tokens[i + 1]
    return image, alias


def _is_pinned(image: str) -> bool:
    """Is this external base image pinned to a concrete tag or digest?

    A digest (``@sha256:...``) is the strongest pin. Otherwise the image must carry a
    tag that is not ``latest``. The tag is the ``:`` segment *after* the last ``/`` —
    so a registry host:port (``reg:5000/img``) is never mistaken for a tag.
    """
    if "@" in image:  # digest-pinned (e.g. name@sha256:...)
        return True
    name = image.rsplit("/", 1)[-1]  # drop any registry/path so host:port ≠ tag
    if ":" not in name:
        return False  # no tag at all — floats to the registry's default
    tag = name.rsplit(":", 1)[-1]
    return tag.lower() != "latest"


@dataclass(frozen=True)
class _ParsedDockerfile:
    """The three facts the hygiene rules judge, extracted from the instruction stream."""

    external_bases: tuple[str, ...]  # FROM refs that aren't earlier stages, in order
    final_stage_user: str | None  # last USER in the final stage (None ⇒ none seen)
    has_healthcheck: bool


def _from_effect(rest: str, known_aliases: set[str]) -> tuple[str | None, str | None]:
    """Interpret a ``FROM`` line: return ``(external_base | None, new_alias | None)``.

    The base is ``None`` when the ``FROM`` references an earlier stage (internal, not an
    external image to pin). The alias (lower-cased) is ``None`` when there's no ``AS``.
    """
    image, alias = _from_image_and_alias(rest)
    base = image if (image and image.lower() not in known_aliases) else None
    return base, (alias.lower() if alias else None)


def _parse(dockerfile: str) -> _ParsedDockerfile:
    """Reduce a Dockerfile to the facts the hygiene rules need."""
    stage_aliases: set[str] = set()
    bases: list[str] = []
    final_stage_user: str | None = None
    has_healthcheck = False
    for op, rest in (_split_instruction(line) for line in _logical_lines(dockerfile)):
        if op == "FROM":
            base, alias = _from_effect(rest, stage_aliases)
            if base:
                bases.append(base)
            if alias:
                stage_aliases.add(alias)
            final_stage_user = None  # a new stage resets the effective USER
        elif op == "USER":
            final_stage_user = _user_name(rest)
        elif op == "HEALTHCHECK" and rest.strip().upper() != "NONE":
            has_healthcheck = True
    return _ParsedDockerfile(tuple(bases), final_stage_user, has_healthcheck)


def _user_name(rest: str) -> str:
    """The user name from a ``USER`` line ('' if none given)."""
    parts = rest.split()
    return parts[0] if parts else ""


def _non_root_finding(final_stage_user: str | None) -> ContainerFinding | None:
    """A finding if the final stage runs as root (no USER, or USER root/0)."""
    if final_stage_user is not None and final_stage_user not in {"root", "0"}:
        return None
    detail = (
        "no USER instruction — the image runs as root"
        if final_stage_user is None
        else f"the final USER is '{final_stage_user}' (root)"
    )
    return ContainerFinding(
        "non_root",
        f"container runs as root: {detail}. Add a non-root `USER` in the final "
        "stage (least privilege).",
    )


def _pinned_base_findings(external_bases: Sequence[str]) -> list[ContainerFinding]:
    """One finding per external base image that isn't pinned to a tag or digest."""
    findings: list[ContainerFinding] = []
    for image in external_bases:
        if image.lower() in _SELF_PINNED_BASES or "$" in image:
            continue  # scratch is self-pinned; a $-variable base can't be judged
        if not _is_pinned(image):
            findings.append(
                ContainerFinding(
                    "pinned_base",
                    f"base image '{image}' is not pinned — pin a concrete tag "
                    "(not `latest`) or a digest for reproducible builds.",
                )
            )
    return findings


def _healthcheck_finding(has_healthcheck: bool) -> ContainerFinding | None:
    """A finding if no HEALTHCHECK is declared."""
    if has_healthcheck:
        return None
    return ContainerFinding(
        "healthcheck",
        "no HEALTHCHECK declared — an orchestrator can't tell a live container "
        "from a wedged one. Add a HEALTHCHECK (or drop the `healthcheck` rule for "
        "a run-and-exit container).",
    )


def hygiene_findings(
    dockerfile: str,
    *,
    require: Sequence[str] = ALL_RULES,
) -> list[ContainerFinding]:
    """Return the container-hygiene violations in ``dockerfile`` for the enforced rules.

    ``require`` selects which rules apply (default: all of :data:`ALL_RULES`). Rules:

    - ``non_root`` — the final build stage must end on a ``USER`` that is not
      ``root``/``0`` (no ``USER`` ⇒ the image runs as root).
    - ``pinned_base`` — every *external* ``FROM`` (not a reference to an earlier
      stage, not ``scratch``, not a ``$``-variable we can't resolve) must be pinned
      to a non-``latest`` tag or a digest.
    - ``healthcheck`` — at least one ``HEALTHCHECK`` (other than ``HEALTHCHECK NONE``)
      must be declared.

    Deterministic and threshold-free. Unknown rule names in ``require`` are ignored.
    """
    enforced = set(require)
    parsed = _parse(dockerfile)
    findings: list[ContainerFinding] = []
    if "non_root" in enforced:
        finding = _non_root_finding(parsed.final_stage_user)
        if finding is not None:
            findings.append(finding)
    if "pinned_base" in enforced:
        findings.extend(_pinned_base_findings(parsed.external_bases))
    if "healthcheck" in enforced:
        finding = _healthcheck_finding(parsed.has_healthcheck)
        if finding is not None:
            findings.append(finding)
    return findings
