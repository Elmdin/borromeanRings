"""Native secret scanning. Example secrets are built at runtime so this file's
source contains no literal token (nothing for the scanner to self-flag). ADR-0032."""

from pathlib import Path

from meta_harness.secrets import scan_files, scan_text

# Constructed at runtime — no literal secret appears in this source file.
_AWS = "AKIA" + "1234567890ABCDEF"
_GH_PAT = "ghp_" + "a" * 36
_PRIVATE_KEY = "-----BEGIN " + "PRIVATE KEY-----"
_GOOGLE = "AIza" + "b" * 35


def test_flags_aws_access_key() -> None:
    found = scan_text(f"aws_key = '{_AWS}'\n")
    assert len(found) == 1
    assert found[0].kind == "aws-access-key-id"
    assert found[0].line == 1


def test_flags_github_pat() -> None:
    assert scan_text(f"token={_GH_PAT}")[0].kind == "github-pat"


def test_flags_private_key_block() -> None:
    assert scan_text(_PRIVATE_KEY)[0].kind == "private-key-block"


def test_flags_google_api_key() -> None:
    assert scan_text(f"key = {_GOOGLE}")[0].kind == "google-api-key"


def test_clean_text_has_no_findings() -> None:
    assert scan_text("just some ordinary code\nx = compute(y)\n") == []


def test_short_lookalikes_do_not_match() -> None:
    # AKIA without the full 16 trailing chars must not match.
    assert scan_text("AKIA123 = 'short'\n") == []


def test_allow_marker_suppresses_a_line() -> None:
    text = f"example = '{_AWS}'  # borromeanrings: allow-secret\n"
    assert scan_text(text) == []


def test_snippet_is_truncated_not_full_secret() -> None:
    finding = scan_text(_GH_PAT)[0]
    assert finding.snippet.endswith("…")
    assert _GH_PAT not in finding.snippet


def test_scan_files_reads_and_skips_binary(tmp_path: Path) -> None:
    good = tmp_path / "a.txt"
    good.write_text(f"k={_AWS}\n")
    binary = tmp_path / "b.bin"
    binary.write_bytes(b"\xff\xfe\x00secret")
    findings = scan_files([good, binary, tmp_path / "missing.txt"])
    assert len(findings) == 1
    assert findings[0].path == str(good)


# --- #230: every pattern is covered by a test, as a table not a memory ---------
#
# The AWS *secret* key gap survived because the coverage of this module was an
# impression rather than a list. Anything added to _PATTERNS without a row here
# is caught by test_every_pattern_has_a_planted_example below.

_AWS_SECRET = "wJalrXUtnFEMI/" + "K7MDENG/bPxRfiCYEXAMPLEKEY"
_SLACK = "xoxb-" + "1234567890abcdef"
_STRIPE = "sk_live_" + "0123456789abcdef"
_SLACK_HOOK = "https://hooks.slack.com/" + "services/T00/B00/XXXX"
_GH_FINE = "github_pat_" + "a" * 82

PLANTED: dict[str, str] = {
    "private-key-block": _PRIVATE_KEY,
    "aws-access-key-id": f"key = '{_AWS}'",
    "aws-secret-access-key": f"AWS_SECRET_ACCESS_KEY = '{_AWS_SECRET}'",
    "github-pat": f"t = '{_GH_PAT}'",
    "github-fine-grained-pat": f"t = '{_GH_FINE}'",
    "slack-token": f"t = '{_SLACK}'",
    "google-api-key": f"t = '{_GOOGLE}'",
    "stripe-secret-key": f"t = '{_STRIPE}'",
    "slack-webhook": f"url = '{_SLACK_HOOK}'",
}


def test_every_pattern_has_a_planted_example() -> None:
    """No pattern may ship without a row above. Coverage is a list, not a belief."""
    from meta_harness.secrets import _PATTERNS

    assert {kind for kind, _ in _PATTERNS} == set(PLANTED)


def test_each_planted_secret_is_detected() -> None:
    for kind, line in PLANTED.items():
        found = scan_text(line)
        assert found, f"{kind}: not detected"
        assert found[0].kind == kind, f"{kind}: matched as {found[0].kind}"


def test_the_aws_secret_key_is_found_where_it_actually_leaks() -> None:
    """Every real home for this credential, not just the one a test author imagines.

    The first version of this pattern required quotes around the value, so it
    missed ``~/.aws/credentials`` — the canonical location for exactly this
    credential, whose INI format has no quotes — along with ``.env`` files,
    Dockerfile ``ENV`` and ``export``. Caught in review. The table is the fix:
    a shape that only matches the form the author happened to picture is a
    scanner that reports "no secrets" over the commonest leak there is.
    """
    for label, line in {
        "aws credentials file (INI)": f"aws_secret_access_key = {_AWS_SECRET}",
        ".env / Dockerfile ENV": f"AWS_SECRET_ACCESS_KEY={_AWS_SECRET}",
        "shell export": f"export AWS_SECRET_ACCESS_KEY={_AWS_SECRET}",
        "python, quoted": f'AWS_SECRET_ACCESS_KEY = "{_AWS_SECRET}"',
        "yaml": f'aws_secret_access_key: "{_AWS_SECRET}"',
        "json": f'"aws_secret_access_key": "{_AWS_SECRET}",',
        "os.environ subscript": f'os.environ["AWS_SECRET_ACCESS_KEY"] = "{_AWS_SECRET}"',
        "camel case": f'AwsSecretKey = "{_AWS_SECRET}"',
    }.items():
        found = scan_text(line)
        assert found, f"missed: {label}"
        assert found[0].kind == "aws-secret-access-key", label


def test_a_longer_base64_run_is_not_truncated_to_a_match() -> None:
    """Requiring a terminator stops a 50-char value matching its first 40."""
    assert not scan_text(f"aws_secret_access_key = {_AWS_SECRET}0123456789")


def test_the_aws_secret_key_is_matched_by_name_and_shape_not_entropy() -> None:
    """The rule this module sets for itself: shapes that almost never occur by accident.

    A bare 40-character base64 string is not such a shape — it is also every
    sha256 and every short blob — so it must NOT be flagged on its own. The
    identifier is what makes the pair high-confidence.
    """
    assert scan_text(f"AWS_SECRET_ACCESS_KEY = '{_AWS_SECRET}'")  # name + shape
    assert scan_text(f"aws_secret_access_key: '{_AWS_SECRET}'")  # yaml/ini spelling
    assert scan_text(f"AwsSecretKey = '{_AWS_SECRET}'")  # camel case

    assert not scan_text(f"BLOB = '{_AWS_SECRET}'")  # shape alone: not a finding
    assert not scan_text("DIGEST = '" + "a3f5c1e9b7d2048f" + "6a1c3e5b7d9f0a2c4e6b8d0f" + "'")
    assert not scan_text("DB_PASSWORD = 'hunter2-correct-horse'")  # generic: excluded


def test_the_allow_marker_is_line_scoped_and_a_formatter_can_break_it() -> None:
    """Pin the sharp edge so it is a known limitation, not a surprise (#230).

    ``ruff format`` — which ``10_format`` runs, and the post-edit hook runs
    unprompted — wraps a long statement and leaves the trailing comment on the
    closing paren, below the literal. The suppression the check's own remedy line
    told the user to add then stops working, with no change in meaning.

    Asserting it here means the day someone gives the marker a scope rule, this
    test fails and tells them to update the docs — rather than the behaviour
    quietly changing under a comment that still claims line scope.
    """
    literal = f"key = '{_AWS}'"
    assert not scan_text(f"{literal}  # borromeanrings: allow-secret")  # on the line
    assert scan_text(f"# borromeanrings: allow-secret\n{literal}")  # a line above: NOT honoured
    assert scan_text(f"{literal}\n# borromeanrings: allow-secret")  # a line below: NOT honoured
