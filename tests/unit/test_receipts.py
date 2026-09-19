"""Receipts are tamper-EVIDENT: a receipt whose verdict fields or log content are
edited after the fact no longer matches its own digest.

This is evidence, not cryptographic proof — the digest algorithm is public, so a
knowledgeable local editor can re-forge receipt+log+digest together. It detects
accidental corruption and naive editing (flip `status` without recomputing), and
yields a single run digest that CI can anchor in its external log. See
meta_harness/receipts.py and ADR-0026.
"""

import json
import shutil
from pathlib import Path

from meta_harness.receipts import (
    CONTENT_HASH_FIELD,
    IntegrityReport,
    compute_content_hash,
    finalize_receipt,
    read_log_text,
    resolve_log_path,
    run_digest,
    verify_dir,
    verify_receipt,
)

_RECEIPT = {
    "check": "20_lint",
    "command": "ruff check .",
    "exit_code": 0,
    "log": "/x/20_lint.log",
    "status": "pass",
}


def test_finalize_then_verify_roundtrips() -> None:
    r = finalize_receipt(_RECEIPT, "all clean\n")
    assert CONTENT_HASH_FIELD in r
    assert verify_receipt(r, "all clean\n")


def test_hash_ignores_the_hash_field_itself() -> None:
    # Recomputing over a finalized receipt must reproduce the stored digest,
    # i.e. the digest does not fold in its own value (which would be circular).
    r = finalize_receipt(_RECEIPT, "log\n")
    assert compute_content_hash(r, "log\n") == r[CONTENT_HASH_FIELD]


def test_flipping_status_is_detected() -> None:
    # Take a genuinely failing receipt and forge it to pass.
    failing = finalize_receipt({**_RECEIPT, "status": "fail", "exit_code": 1}, "boom\n")
    tampered = {**failing, "status": "pass", "exit_code": 0}
    assert not verify_receipt(tampered, "boom\n")


def test_editing_the_log_is_detected() -> None:
    r = finalize_receipt(_RECEIPT, "original log\n")
    assert not verify_receipt(r, "edited log\n")


def test_unhashed_receipt_does_not_verify() -> None:
    assert not verify_receipt(dict(_RECEIPT), "log\n")  # no CONTENT_HASH_FIELD


def test_extra_fields_are_covered_by_the_hash() -> None:
    # e.g. 40_test adds coverage_percent; forging it must be detected.
    base = finalize_receipt({**_RECEIPT, "coverage_percent": 91.2}, "log\n")
    forged = {**base, "coverage_percent": 10.0}
    assert not verify_receipt(forged, "log\n")


def test_run_digest_is_order_independent_and_deterministic() -> None:
    assert run_digest(["a", "b", "c"]) == run_digest(["c", "a", "b"])
    assert run_digest(["a", "b"]) != run_digest(["a", "c"])


def _emit(dir_: Path, name: str, receipt: dict, log_text: str) -> None:
    (dir_ / f"{name}.log").write_text(log_text)
    r = {**receipt, "log": str(dir_ / f"{name}.log")}
    (dir_ / f"{name}.json").write_text(json.dumps(finalize_receipt(r, log_text)))


def test_verify_dir_all_good(tmp_path: Path) -> None:
    _emit(tmp_path, "20_lint", _RECEIPT, "clean\n")
    _emit(tmp_path, "05_hygiene", {**_RECEIPT, "check": "05_hygiene"}, "ok\n")
    report = verify_dir(tmp_path)
    assert isinstance(report, IntegrityReport)
    assert report.ok
    assert report.tampered == ()


def test_verify_dir_flags_a_tampered_receipt(tmp_path: Path) -> None:
    _emit(tmp_path, "20_lint", _RECEIPT, "clean\n")
    # Post-hoc edit the JSON to flip status without recomputing the digest.
    jf = tmp_path / "20_lint.json"
    data = json.loads(jf.read_text())
    data["status"] = "fail"
    jf.write_text(json.dumps(data))
    report = verify_dir(tmp_path)
    assert not report.ok
    assert "20_lint" in report.tampered


def test_verify_dir_flags_missing_log(tmp_path: Path) -> None:
    _emit(tmp_path, "20_lint", _RECEIPT, "clean\n")
    (tmp_path / "20_lint.log").unlink()
    report = verify_dir(tmp_path)
    assert "20_lint" in report.missing_log
    assert not report.ok


def test_verify_dir_flags_corrupt_json(tmp_path: Path) -> None:
    (tmp_path / "20_lint.json").write_text("{not valid json")
    report = verify_dir(tmp_path)
    assert "20_lint" in report.tampered
    assert not report.ok


def test_verify_dir_flags_unhashed_receipt(tmp_path: Path) -> None:
    # A receipt file written without a content hash at all (e.g. a legacy or
    # hand-crafted receipt) must be flagged, never silently trusted.
    (tmp_path / "20_lint.log").write_text("clean\n")
    (tmp_path / "20_lint.json").write_text(
        json.dumps({**_RECEIPT, "log": str(tmp_path / "20_lint.log")})
    )
    report = verify_dir(tmp_path)
    assert "20_lint" in report.unhashed
    assert not report.ok


# --------------------------------------------------------------------------
# Reader-side log resolution (transported bundles — SPEC-executor §2.3, ADR-0076)
# --------------------------------------------------------------------------


def test_resolve_log_path_prefers_the_recorded_path(tmp_path: Path) -> None:
    recorded = tmp_path / "20_lint.log"
    recorded.write_text("clean\n")
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "20_lint.log").write_text("different\n")
    assert resolve_log_path(str(recorded), other) == recorded


def test_resolve_log_path_falls_back_to_the_basename_in_the_receipt_dir(tmp_path: Path) -> None:
    # The worktree/sandbox case: the recorded path is where the log WAS.
    landed = tmp_path / "20_lint.log"
    landed.write_text("clean\n")
    assert resolve_log_path("/gone/run-42/20_lint.log", tmp_path) == landed


def test_resolve_log_path_is_none_when_neither_exists(tmp_path: Path) -> None:
    assert resolve_log_path("/gone/run-42/20_lint.log", tmp_path) is None


def test_resolve_log_path_is_none_for_an_empty_recorded_path(tmp_path: Path) -> None:
    assert resolve_log_path("", tmp_path) is None


def test_read_log_text_reads_the_resolved_log(tmp_path: Path) -> None:
    (tmp_path / "20_lint.log").write_text("clean\n")
    assert read_log_text({"log": "/gone/20_lint.log"}, tmp_path) == "clean\n"


def test_read_log_text_is_empty_when_unresolvable(tmp_path: Path) -> None:
    assert read_log_text({"log": "/gone/20_lint.log"}, tmp_path) == ""


def test_read_log_text_is_empty_when_the_receipt_has_no_log_field(tmp_path: Path) -> None:
    assert read_log_text({}, tmp_path) == ""


def test_read_log_text_is_empty_when_the_log_is_unreadable(tmp_path: Path) -> None:
    # A directory where the log should be: unreadable, so the hash check sees ""
    # and the receipt fails closed rather than raising.
    (tmp_path / "20_lint.log").mkdir()
    assert read_log_text({"log": "/gone/20_lint.log"}, tmp_path) == ""


def test_a_transported_bundle_still_verifies(tmp_path: Path) -> None:
    # Emit in one directory, move the whole bundle to another (what the worktree
    # executor's copy-back does), and verify: the recorded path is gone, the log
    # sits beside its receipt, integrity holds.
    origin = tmp_path / "worktree-run"
    origin.mkdir()
    _emit(origin, "20_lint", _RECEIPT, "clean\n")
    landed = tmp_path / "primary-run"
    shutil.move(str(origin), str(landed))
    receipt = json.loads((landed / "20_lint.json").read_text())
    assert not Path(str(receipt["log"])).exists()
    assert verify_receipt(receipt, read_log_text(receipt, landed))
    assert verify_dir(landed).ok


def test_a_transported_bundle_with_an_edited_log_still_fails(tmp_path: Path) -> None:
    # The fallback resolves WHERE the log is, never WHAT it says: tamper evidence
    # is unweakened by transport.
    origin = tmp_path / "worktree-run"
    origin.mkdir()
    _emit(origin, "20_lint", _RECEIPT, "clean\n")
    landed = tmp_path / "primary-run"
    shutil.move(str(origin), str(landed))
    (landed / "20_lint.log").write_text("all clean, honest\n")
    receipt = json.loads((landed / "20_lint.json").read_text())
    assert not verify_receipt(receipt, read_log_text(receipt, landed))
    report = verify_dir(landed)
    assert not report.ok
    assert report.tampered == ("20_lint",)
