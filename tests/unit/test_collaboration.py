"""Tests for Tier A collaboration gates (docs/specs/SPEC-collaboration.md, ADR-0021)."""

from meta_harness.collaboration import branch_violation, commit_violations

PATTERNS = ("feat/*", "fix/*", "docs/*", "chore/*", "hotfix/*")
PROTECTED = ("main", "dev")
TYPES = ("feat", "fix", "refactor", "docs", "test", "chore", "perf", "ci")


# --- branch naming ------------------------------------------------------------


def test_branch_matching_a_pattern_passes() -> None:
    assert branch_violation("feat/tier-a-collaboration", PROTECTED, PATTERNS) is None
    assert branch_violation("fix/hooks-hygiene", PROTECTED, PATTERNS) is None


def test_branch_matching_no_pattern_fails() -> None:
    violation = branch_violation("my-cool-branch", PROTECTED, PATTERNS)
    assert violation is not None
    assert "my-cool-branch" in violation
    assert "feat/*" in violation  # tells the author what IS allowed


def test_protected_branches_are_skipped() -> None:
    # CI runs on main/dev post-merge; naming rules apply to work branches only.
    assert branch_violation("main", PROTECTED, PATTERNS) is None
    assert branch_violation("dev", PROTECTED, PATTERNS) is None


def test_detached_head_is_skipped() -> None:
    # PR CI checks out a detached merge ref; there is no branch name to judge.
    assert branch_violation("HEAD", PROTECTED, PATTERNS) is None
    assert branch_violation("", PROTECTED, PATTERNS) is None


def test_undeclared_patterns_turn_the_rule_off() -> None:
    assert branch_violation("anything-goes", PROTECTED, ()) is None


# --- commit messages (Conventional Commits) -----------------------------------


def test_conforming_subjects_pass() -> None:
    commits = [
        ("a" * 40, "feat: add Tier A collaboration checks"),
        ("b" * 40, "fix(hooks): bound the stdin read"),
        ("c" * 40, "docs: collaboration-governance spec"),
        ("d" * 40, "feat!: drop the legacy manifest"),
    ]
    assert commit_violations(commits, TYPES, 72) == []


def test_unknown_type_fails() -> None:
    violations = commit_violations([("a" * 40, "feature: wrong type word")], TYPES, 72)
    assert len(violations) == 1
    assert "aaaaaaaa" in violations[0]  # short sha for locating the commit
    assert "feature" in violations[0]


def test_missing_colon_fails() -> None:
    violations = commit_violations([("b" * 40, "add stuff without a type")], TYPES, 72)
    assert len(violations) == 1


def test_empty_subject_after_type_fails() -> None:
    assert len(commit_violations([("c" * 40, "feat: ")], TYPES, 72)) == 1


def test_overlong_subject_fails() -> None:
    long_subject = "feat: " + "x" * 80
    violations = commit_violations([("d" * 40, long_subject)], TYPES, 72)
    assert len(violations) == 1
    assert "72" in violations[0]


def test_zero_max_length_disables_the_length_rule() -> None:
    long_subject = "feat: " + "x" * 200
    assert commit_violations([("e" * 40, long_subject)], TYPES, 0) == []


def test_undeclared_types_turn_the_rule_off() -> None:
    assert commit_violations([("f" * 40, "whatever, no convention")], (), 72) == []


def test_each_bad_commit_is_reported() -> None:
    commits = [
        ("1" * 40, "feat: fine"),
        ("2" * 40, "bogus: not a type"),
        ("3" * 40, "also not conventional"),
    ]
    assert len(commit_violations(commits, TYPES, 72)) == 2
