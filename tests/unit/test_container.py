"""Unit tests for container (Dockerfile) hygiene (meta_harness.container)."""

from __future__ import annotations

from meta_harness.container import ALL_RULES, ContainerFinding, hygiene_findings


def _rules(findings: list[ContainerFinding]) -> set[str]:
    return {f.rule for f in findings}


# A well-formed service image: non-root, pinned base, healthcheck present.
CLEAN_SERVICE = """\
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
RUN useradd --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser
HEALTHCHECK --interval=30s CMD python -m myapp.health
ENTRYPOINT ["python", "-m", "myapp"]
"""


def test_clean_service_has_no_findings() -> None:
    assert hygiene_findings(CLEAN_SERVICE) == []


def test_missing_user_is_flagged_as_root() -> None:
    dockerfile = 'FROM python:3.12-slim\nHEALTHCHECK CMD true\nCMD ["true"]\n'
    findings = hygiene_findings(dockerfile)
    assert "non_root" in _rules(findings)
    assert any("root" in f.message.lower() for f in findings)


def test_explicit_root_user_is_flagged() -> None:
    dockerfile = "FROM python:3.12-slim\nUSER root\nHEALTHCHECK CMD true\n"
    assert "non_root" in _rules(hygiene_findings(dockerfile))
    # numeric root too
    assert "non_root" in _rules(hygiene_findings("FROM x:1\nUSER 0\nHEALTHCHECK CMD true\n"))


def test_latest_and_untagged_bases_are_unpinned() -> None:
    assert "pinned_base" in _rules(
        hygiene_findings("FROM python:latest\nUSER app\nHEALTHCHECK CMD true\n")
    )
    assert "pinned_base" in _rules(
        hygiene_findings("FROM ubuntu\nUSER app\nHEALTHCHECK CMD true\n")
    )


def test_digest_and_concrete_tag_are_pinned() -> None:
    tagged = "FROM python:3.12-slim\nUSER app\nHEALTHCHECK CMD true\n"
    digest = "FROM python@sha256:abcdef\nUSER app\nHEALTHCHECK CMD true\n"
    assert "pinned_base" not in _rules(hygiene_findings(tagged))
    assert "pinned_base" not in _rules(hygiene_findings(digest))


def test_registry_port_is_not_mistaken_for_a_tag() -> None:
    # host:port/name with no tag → still unpinned; host:port/name:tag → pinned.
    unpinned = "FROM registry.local:5000/app\nUSER app\nHEALTHCHECK CMD true\n"
    pinned = "FROM registry.local:5000/app:1.4.2\nUSER app\nHEALTHCHECK CMD true\n"
    assert "pinned_base" in _rules(hygiene_findings(unpinned))
    assert "pinned_base" not in _rules(hygiene_findings(pinned))


def test_scratch_and_variable_bases_are_not_flagged() -> None:
    # scratch is self-pinned; a $-variable base can't be judged statically.
    assert "pinned_base" not in _rules(
        hygiene_findings("FROM scratch\nUSER app\nHEALTHCHECK CMD true\n")
    )
    assert "pinned_base" not in _rules(
        hygiene_findings("FROM ${BASE}\nUSER app\nHEALTHCHECK CMD true\n")
    )


def test_missing_healthcheck_is_flagged_and_none_disables() -> None:
    no_hc = "FROM python:3.12-slim\nUSER app\n"
    assert "healthcheck" in _rules(hygiene_findings(no_hc))
    # HEALTHCHECK NONE explicitly opts out → treated as absent.
    assert "healthcheck" in _rules(
        hygiene_findings("FROM python:3.12-slim\nUSER app\nHEALTHCHECK NONE\n")
    )


def test_require_narrows_the_enforced_rule_set() -> None:
    # A run-and-exit container: enforce non_root + pinned_base, not healthcheck.
    dockerfile = "FROM python:3.12-slim\nUSER app\n"  # no healthcheck
    findings = hygiene_findings(dockerfile, require=("non_root", "pinned_base"))
    assert findings == []
    # Full set catches the missing healthcheck.
    assert "healthcheck" in _rules(hygiene_findings(dockerfile, require=ALL_RULES))


def test_multistage_uses_the_final_stage_user() -> None:
    # A non-root USER in the BUILD stage does not make the final image non-root.
    dockerfile = """\
FROM golang:1.22 AS build
USER nobody
RUN go build -o /app ./...
FROM gcr.io/distroless/base:nonroot
COPY --from=build /app /app
HEALTHCHECK CMD ["/app", "health"]
"""
    # final stage has no USER → root, despite the build stage's USER nobody.
    assert "non_root" in _rules(hygiene_findings(dockerfile))


def test_multistage_final_stage_ref_is_not_treated_as_external_base() -> None:
    # `FROM base` referencing an earlier stage alias is internal, not an unpinned base.
    dockerfile = """\
FROM python:3.12-slim AS base
FROM base AS final
USER app
HEALTHCHECK CMD true
"""
    assert "pinned_base" not in _rules(hygiene_findings(dockerfile))


def test_line_continuations_and_comments_are_handled() -> None:
    dockerfile = """\
# a comment
FROM python:3.12-slim
RUN pip install \\
    one \\
    two
# another comment
USER app
HEALTHCHECK CMD true
"""
    assert hygiene_findings(dockerfile) == []


def test_case_insensitive_instructions() -> None:
    dockerfile = "from python:3.12-slim\nuser app\nhealthcheck cmd true\n"
    assert hygiene_findings(dockerfile) == []


def test_blank_lines_are_ignored() -> None:
    dockerfile = "FROM python:3.12-slim\n\n\nUSER app\n\nHEALTHCHECK CMD true\n"
    assert hygiene_findings(dockerfile) == []


def test_trailing_continuation_is_flushed() -> None:
    # A Dockerfile whose last logical line is an unterminated continuation.
    dockerfile = "FROM python:3.12-slim\nUSER app\nHEALTHCHECK CMD true\nRUN echo done \\"
    assert hygiene_findings(dockerfile) == []


def test_malformed_from_with_no_image_is_ignored() -> None:
    # A bare `FROM` contributes no external base (nothing to pin), and the missing
    # USER/HEALTHCHECK still surface for the other rules.
    dockerfile = "FROM\nUSER app\nHEALTHCHECK CMD true\n"
    assert "pinned_base" not in _rules(hygiene_findings(dockerfile))


def test_single_rule_on_a_clean_dockerfile_yields_nothing() -> None:
    # Exercises the "rule enforced but no violation" path for each rule alone.
    clean = "FROM python:3.12-slim\nUSER app\nHEALTHCHECK CMD true\n"
    for rule in ALL_RULES:
        assert hygiene_findings(clean, require=(rule,)) == []
