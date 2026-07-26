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
