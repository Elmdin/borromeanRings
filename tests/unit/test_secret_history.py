"""Unit tests for git-history secret scanning (meta_harness.secret_history)."""

from __future__ import annotations

from meta_harness.secret_history import fingerprint, scan_blobs

# A high-confidence shape the native scanner recognises (AWS access key id).
AWS = "AKIA" + "1234567890ABCDEF"
BLOB_WITH_SECRET = f"aws_key = '{AWS}'\n"


def test_finds_a_secret_in_a_blob() -> None:
    findings = scan_blobs([("blob1", BLOB_WITH_SECRET)])
    assert len(findings) == 1
    assert findings[0].kind == "aws-access-key-id"
    assert findings[0].blob == "blob1"
    assert len(findings[0].fingerprint) == 16  # short, stable id


def test_clean_blobs_yield_nothing() -> None:
    assert scan_blobs([("b", "just some code\n"), ("c", "no secrets here\n")]) == []


def test_same_secret_across_blobs_is_reported_once() -> None:
    # The same file's secret recurs in every historical revision — dedup to one.
    findings = scan_blobs([("older", BLOB_WITH_SECRET), ("newer", BLOB_WITH_SECRET)])
    assert len(findings) == 1
    assert findings[0].blob == "older"  # attributed to the first blob it was seen in


def test_allowlisting_the_findings_fingerprint_drops_it() -> None:
    # Round-trip: scan to learn the fingerprint, then allowlist exactly it.
    fp = scan_blobs([("blob1", BLOB_WITH_SECRET)])[0].fingerprint
    assert scan_blobs([("blob1", BLOB_WITH_SECRET)], allow=[fp]) == []


def test_unrelated_allowlist_entry_does_not_drop_it() -> None:
    assert len(scan_blobs([("blob1", BLOB_WITH_SECRET)], allow=["deadbeefdeadbeef"])) == 1


def test_fingerprint_is_stable_and_one_way() -> None:
    fp = fingerprint("aws-access-key-id", AWS)
    assert fp == fingerprint("aws-access-key-id", AWS)  # deterministic
    assert AWS not in fp and len(fp) == 16  # hides the secret, short
    assert fp != fingerprint("aws-access-key-id", AWS + "X")  # sensitive to input
