"""Unit tests for meta_harness.executor — the executor-conformance helpers.

Exact-value tests: every assertion pins the precise string/tuple the helper
returns, so a mutant that changes a token, a message, or a comparison rule dies.
"""

from pathlib import Path

from meta_harness.executor import (
    DURATION_MASK,
    EXECUTOR_FIELD_PREFIX,
    NAMESPACE_ORIGIN,
    VOLATILE_FIELDS,
    canonicalise_log,
    import_shadow_violation,
    receipt_differences,
)


def test_volatile_fields_are_exactly_log_and_content_hash() -> None:
    assert VOLATILE_FIELDS == ("log", "content_sha256")


def test_executor_field_prefix_is_executor() -> None:
    assert EXECUTOR_FIELD_PREFIX == "executor"


def test_duration_mask_is_angle_t() -> None:
    assert DURATION_MASK == "<T>"


# --------------------------------------------------------------------------
# canonicalise_log
# --------------------------------------------------------------------------


def test_canonicalise_log_without_replacements_masks_durations_only() -> None:
    assert canonicalise_log("12 passed in 0.83s\n") == "12 passed in <T>\n"


def test_canonicalise_log_masks_every_duration_occurrence() -> None:
    assert canonicalise_log("ran 1.50s then 22.75s") == "ran <T> then <T>"


def test_canonicalise_log_leaves_integer_seconds_alone() -> None:
    # Only the `N.Ns` shape is a duration; `300s` is the declared timeout bound
    # and must stay readable in the log.
    assert canonicalise_log("TIMED OUT after 300s") == "TIMED OUT after 300s"


def test_canonicalise_log_applies_replacements() -> None:
    text = "wrote /proj/.meta-harness/receipts/r1/coverage.json under /proj"
    out = canonicalise_log(
        text, (("/proj", "<ROOT>"), ("/proj/.meta-harness/receipts/r1", "<RUN>"))
    )
    assert out == "wrote <RUN>/coverage.json under <ROOT>"


def test_canonicalise_log_replaces_longest_needle_first_whatever_the_order() -> None:
    # The run dir lives *inside* the project root; replacing the root first would
    # leave a half-substituted path and hide a real divergence.
    text = "/proj/run/x.log"
    pairs = (("/proj/run", "<RUN>"), ("/proj", "<ROOT>"))
    assert canonicalise_log(text, pairs) == canonicalise_log(text, tuple(reversed(pairs)))
    assert canonicalise_log(text, pairs) == "<RUN>/x.log"


def test_canonicalise_log_ignores_empty_needles() -> None:
    assert canonicalise_log("abc", (("", "<X>"),)) == "abc"


def test_canonicalise_log_replaces_all_occurrences_of_a_needle() -> None:
    assert canonicalise_log("/p and /p", (("/p", "<R>"),)) == "<R> and <R>"


# --------------------------------------------------------------------------
# receipt_differences
# --------------------------------------------------------------------------


def _receipt(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "check": "20_lint",
        "command": "ruff check .",
        "exit_code": 0,
        "log": "/a/20_lint.log",
        "status": "pass",
        "content_sha256": "deadbeef",
    }
    base.update(over)
    return base


def test_receipt_differences_empty_for_receipts_equal_modulo_volatile_fields() -> None:
    a = _receipt()
    b = _receipt(log="/b/20_lint.log", content_sha256="cafe")
    assert receipt_differences(a, b) == ()


def test_receipt_differences_reports_status_and_exit_code() -> None:
    assert receipt_differences(_receipt(), _receipt(status="fail", exit_code=1)) == (
        "exit_code: 0 != 1",
        "status: 'pass' != 'fail'",
    )


def test_receipt_differences_reports_a_field_only_the_reference_has() -> None:
    assert receipt_differences(_receipt(score=0.9), _receipt()) == (
        "score: only in reference (0.9)",
    )


def test_receipt_differences_reports_a_field_only_the_candidate_has() -> None:
    assert receipt_differences(_receipt(), _receipt(score=0.9)) == (
        "score: only in candidate (0.9)",
    )


def test_receipt_differences_compares_check_specific_extras_exactly() -> None:
    assert receipt_differences(
        _receipt(coverage_percent=99.9), _receipt(coverage_percent=99.8)
    ) == ("coverage_percent: 99.9 != 99.8",)


def test_receipt_differences_ignores_executor_namespaced_extras() -> None:
    assert receipt_differences(_receipt(), _receipt(executor_kind="worktree")) == ()


def test_receipt_differences_honours_a_custom_ignored_set() -> None:
    a = _receipt(status="pass")
    b = _receipt(status="fail")
    assert receipt_differences(a, b, ignored=("log", "content_sha256", "status")) == ()


def test_receipt_differences_does_not_ignore_log_when_ignored_is_narrowed() -> None:
    a = _receipt()
    b = _receipt(log="/b/20_lint.log")
    assert receipt_differences(a, b, ignored=("content_sha256",)) == (
        "log: '/a/20_lint.log' != '/b/20_lint.log'",
    )


# --------------------------------------------------------------------------
# import_shadow_violation
# --------------------------------------------------------------------------


def test_import_shadow_violation_none_when_nothing_resolved() -> None:
    assert import_shadow_violation("", "/wt") is None


def test_import_shadow_violation_none_when_module_is_inside_the_worktree(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    (wt / "src" / "pkg").mkdir(parents=True)
    origin = wt / "src" / "pkg" / "__init__.py"
    origin.touch()
    assert import_shadow_violation(str(origin), str(wt)) is None


def test_import_shadow_violation_message_names_both_paths(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    primary = tmp_path / "primary" / "src" / "pkg" / "__init__.py"
    primary.parent.mkdir(parents=True)
    primary.touch()
    assert import_shadow_violation(str(primary), str(wt)) == (
        f"import shadow: the package resolves to {primary}, outside the worktree {wt} — "
        "an editable install points at the primary checkout, so the run would test the "
        "primary's code and report it against this snapshot"
    )


def test_import_shadow_violation_none_when_module_is_the_worktree_itself(tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    assert import_shadow_violation(str(wt), str(wt)) is None


def test_import_shadow_violation_none_for_a_namespace_package() -> None:
    # A namespace package has no single origin; the guard cannot judge it and says
    # so by returning None rather than guessing. Documented limit, not a silent pass.
    assert import_shadow_violation(NAMESPACE_ORIGIN, "/wt") is None
    assert NAMESPACE_ORIGIN == "namespace"


def test_import_shadow_violation_still_flags_a_path_named_like_the_namespace_marker(
    tmp_path: Path,
) -> None:
    # Only the exact marker is exempt: a real file whose name merely contains
    # "namespace" is still compared against the worktree.
    wt = tmp_path / "wt"
    wt.mkdir()
    outside = tmp_path / "primary" / "namespace_pkg.py"
    outside.parent.mkdir()
    outside.touch()
    assert import_shadow_violation(str(outside), str(wt)) is not None
