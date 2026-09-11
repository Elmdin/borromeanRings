"""The generator loop's decision core — who produces the next change, bounded.

borromeanRings drives one loop: *generate → gate → retry → escalate*. Two adapters sit
in the generator's seat — the Stop-hooked agent (``.claude/hooks/stop_gate.sh``) and the
headless driver (``generate.sh``) — and the loop's rules must not be a property of
either script. This module is where they live:

* :data:`CAP` — the retry bound, declared **once** and read by both adapters, so no
  adapter can quietly grant itself a fourth attempt;
* :func:`next_action` — the whole decision, pure: no clock, no filesystem, no
  subprocess. Given what the generator did and what the gate said, it returns what
  happens next. Ambiguous counts raise rather than resolve themselves into a pass;
* :func:`read_generator` — the self-declared provenance label (ADR-0071 §4). Absent
  means ``""``, never a guess: the gate records who claimed to write the change and
  makes **no decision** on it (ADR-0049: the generator's word is not evidence);
* :func:`failing_check_ids` — the retry request's check names, read off the verdict's
  own rows so a summary-format change can never silently drop one;
* :func:`snapshot_evidence` / :func:`evidence_writes` — the driver's proof that the
  generator did not write under ``.meta-harness/``. The attempt counter lives there,
  and an unbounded retry loop is the one failure a human cannot un-spend.

What is deliberately NOT here: running the generator, running the gate, the clock and
the attempt counter's file. Those are the thin shell drivers' (``generate.sh``,
``stop_gate.sh``). See docs/specs/SPEC-generator.md and ADR-0071/ADR-0078.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from stat import S_IFMT, S_ISLNK, S_ISREG

from meta_harness.verdict import Verdict, is_failing

#: The retry bound, shared by every generator adapter. Three attempts, then a human.
#: A generator cannot raise it: it is not passed in from the environment or the config.
CAP = 3

#: The gate accepted the change; the loop is done.
ACTION_GREEN = "green"
#: The gate refused and attempts remain; deliver the verdict and ask again.
ACTION_RETRY = "retry"
#: Hand control to the human — the cap is spent, or the generator has nothing to add.
ACTION_ESCALATED = "escalated"
#: The generator itself failed (crashed, timed out, or could not be trusted).
ACTION_GENERATOR_FAILED = "generator-failed"

#: Every outcome :func:`next_action` can return, in decision order.
ACTIONS = (ACTION_GREEN, ACTION_RETRY, ACTION_ESCALATED, ACTION_GENERATOR_FAILED)

#: Longest provenance label recorded. A label, not a payload — a self-declared string
#: goes into every verdict record, so it is bounded before it gets there.
MAX_GENERATOR_LENGTH = 128

#: Bytes read at a time when hashing an evidence file. Receipt logs run to megabytes.
HASH_CHUNK_BYTES = 65536


def next_action(attempt: int, cap: int, gate_ok: bool, tree_changed: bool, exit_code: int) -> str:
    """What the loop does next, from what just happened. Pure.

    The order of the rules *is* the contract, and each one outranks everything below it:

    1. a non-zero ``exit_code`` is the generator saying it could not (N4) — no gate
       result and no remaining attempt can redeem it;
    2. exit 0 with an unchanged tree is the generator saying it *would* not; retrying an
       idempotent generator only spends attempts, so escalate now (N4);
    3. a green gate ends the loop, on the last attempt as much as the first;
    4. at or beyond the cap, the human takes over (N5);
    5. otherwise, retry.

    ``gate_ok`` is read only once rules 1 and 2 have passed, so a driver that skipped the
    gate (because it had nothing to gate) may pass anything for it.

    Args:
        attempt: 1-based attempt number just completed.
        cap: the retry bound for this run — :data:`CAP` for both shipped adapters.
        gate_ok: did the gate pass? Ignored unless the generator wrote a change.
        tree_changed: did the generator change the working tree?
        exit_code: the generator command's exit status (0 = it says it wrote a change).

    Returns:
        One of :data:`ACTIONS`.

    Raises:
        ValueError: if ``attempt`` or ``cap`` is below 1. An impossible count is an
            ambiguous state, and an ambiguous state is never resolved into a pass.
    """
    if attempt < 1 or cap < 1:
        raise ValueError(
            f"attempt and cap are 1-based and must be positive (got attempt={attempt}, cap={cap})"
        )
    if exit_code != 0:
        return ACTION_GENERATOR_FAILED
    if not tree_changed:
        return ACTION_ESCALATED
    if gate_ok:
        return ACTION_GREEN
    if attempt >= cap:
        return ACTION_ESCALATED
    return ACTION_RETRY


def read_generator(raw: str | None) -> str:
    """The provenance label to record for this run; unusable or absent ⇒ ``""``.

    Self-declared by whichever adapter runs the gate (``<kind>:<id>`` by convention —
    ``claude-code:<session_id>``, ``headless:<command basename>``), exactly like a git
    author line. The kind is deliberately **not** validated against an allowlist: the
    gate makes no decision on this field, and validating it would be a decision.

    What is enforced is only that the label cannot damage the record it goes into: outer
    whitespace is dropped, a value carrying any control character is refused outright
    (it would corrupt the verdict's JSON or a terminal reading it), and the result is
    truncated to :data:`MAX_GENERATOR_LENGTH`.

    Args:
        raw: the raw ``BORROMEANRINGS_GENERATOR`` value, or ``None`` when unset.

    Returns:
        The label to record, or ``""`` — never a guess at who the generator was.
    """
    if not raw:
        return ""
    value = raw.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return ""
    return value[:MAX_GENERATOR_LENGTH]


def failing_check_ids(checks: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """The check ids a verdict's rows report as failing, in the verdict's own order.

    The retry request must name every failing check (N2). Deriving the names from the
    persisted rows rather than from the printed summary means a change to how the
    summary is formatted cannot silently drop one.

    Args:
        checks: ``(check_id, status)`` rows as the verdict records them.

    Returns:
        The ids whose status fails the run, by :func:`meta_harness.verdict.is_failing`
        (fail-closed: an unknown status counts as failing).
    """
    return tuple(check_id for check_id, status in checks if is_failing(status))


def _content_hash(path: Path) -> str:
    """SHA-256 of a file, read in chunks so a megabyte-scale log costs no memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_evidence(root: Path | str) -> dict[str, str]:
    """Fingerprint every file under ``root``: ``{relative path: "<size>:<sha256>"}``.

    Taken by the driver either side of the generator's run, over the gate's evidence
    area (``.meta-harness/``). The fingerprint is the file's **content**, not its size and
    mtime: a generator can write ``0`` over ``2`` in the attempt counter and then
    ``os.utime`` the nanoseconds back, and a size-and-mtime reading goes silent on exactly
    the tamper it exists to catch. Hashing costs a read of the evidence area per attempt
    and is the only reading that cannot be restored.

    Nothing is excluded, and nothing is skipped for being the wrong kind of file. The
    driver keeps its own capture of the generator's output outside this directory until
    after the comparison, so "nothing under ``.meta-harness/`` moved" is literally true
    rather than true-apart-from-one-path the generator could compute — and it is true of
    *entries*, not of regular files specifically: a directory or a symlink appearing where
    there was none is somewhere to write, and a symlink is recorded as itself rather than
    as whatever it aims at, because ``rglob`` will not descend into one.

    Args:
        root: directory to fingerprint; a missing one yields ``{}`` (a project that has
            never been gated has no evidence area, which is not a fault).

    Returns:
        A mapping suitable for :func:`evidence_writes`.
    """
    base = Path(root)
    snapshot: dict[str, str] = {}
    if not base.is_dir():
        return snapshot
    for path in base.rglob("*"):
        try:
            # lstat, so a symlink is recorded as itself rather than as its target.
            info = path.lstat()
            key = str(path.relative_to(base))
            if S_ISREG(info.st_mode):
                snapshot[key] = f"{info.st_size}:{_content_hash(path)}"
            elif S_ISLNK(info.st_mode):
                snapshot[key] = f"link:{os.readlink(path)}"
            else:
                snapshot[key] = f"type:{S_IFMT(info.st_mode)}"
        except OSError:
            continue  # unreadable now ⇒ it drops out, and dropping out reads as a write
    return snapshot


def evidence_writes(before: Mapping[str, str], after: Mapping[str, str]) -> tuple[str, ...]:
    """Every difference between two :func:`snapshot_evidence` readings, as reasons. Pure.

    Empty means the generator kept its hands off the gate's evidence. Anything else is a
    conformance violation (SPEC-generator.md §5.5): the attempt counter, the receipts
    and the last verdict are the gate's, and a generator that edits them has forged the
    only thing standing between a looping agent and a human's afternoon.

    Args:
        before: the reading taken before the generator ran.
        after: the reading taken after it exited.

    Returns:
        Sorted ``"<added|removed|modified>: <path>"`` lines; ``()`` when nothing moved.
    """
    reasons = []
    for name in sorted(set(before) | set(after)):
        if name not in before:
            reasons.append(f"added: {name}")
        elif name not in after:
            reasons.append(f"removed: {name}")
        elif before[name] != after[name]:
            reasons.append(f"modified: {name}")
    return tuple(reasons)


def attempts_from_history(checks: Sequence[tuple[str, bool]], generator: str) -> int:
    """How many attempts ``generator`` has already spent, from the gate's own history.

    The attempt counter is one small file, and a generator runs as the same user in the
    same tree: it can delete it. Anchoring to the gate's verdict history as well
    (ADR-0047) means deleting the counter alone no longer resets the bound — the higher of
    the two wins (:func:`attempt_number`).

    **What this is not.** It is a second file in the same tree, not a second authority. A
    review demonstrated three one-command defeats: delete the history, **append one forged
    green row for this label**, or relabel the rows. Appending is the worst, because
    appending is the file's sanctioned operation and the label is not secret — it is the
    filename under ``stop_attempts/`` and plaintext in every row. So the honest claim is
    narrow: the bound now costs two operations instead of one, and one of them writes a
    lie into the record a human reads. It is a speed bump against accident and
    carelessness, **not** a bound against a generator that means to break it. A real one
    needs the count somewhere the generator cannot reach — issue #218.

    Counts the trailing run of failures attributed to this exact generator, stopping at
    its last green. Rows belonging to other generators are skipped, not counted, so two
    sessions in one project keep independent bounds — the ``claude-code:<session_id>``
    label is what makes that work. An unattributed row (``""``) matches nothing.

    Args:
        checks: ``(generator, ok)`` rows from the verdict history, oldest first.
        generator: the provenance label to count for; ``""`` counts nothing.

    Returns:
        Attempts already spent, ``0`` when the last run for this generator was green.
    """
    if not generator:
        return 0
    spent = 0
    for label, ok in reversed(checks):
        if label != generator:
            continue
        if ok:
            break
        spent += 1
    return spent


def attempt_number(counter_value: str | None, history_spent: int) -> int:
    """Which attempt a failing run is, from the counter file and the history together.

    The counter file records attempts *before* this run, so it is incremented here; the
    history already contains this run's verdict, so it is not. Whichever is higher wins:
    a deleted or rewritten counter cannot lower the count below what the ledger shows.

    Args:
        counter_value: the raw contents of the attempt-counter file, or ``None``/``""``
            when it is absent — unreadable is treated as zero *spent*, never as a licence.
        history_spent: :func:`attempts_from_history` for this generator.

    Returns:
        The 1-based attempt number to hand :func:`next_action`. Never below 1.
    """
    previous = 0
    if counter_value is not None:
        # ASCII digits only: "٣".isdigit() is True and int() reads it as 3, which would
        # let a hand-written counter carry a value no shell wrote.
        raw = counter_value.strip()
        if raw.isascii() and raw.isdigit():
            previous = int(raw)
    # No floor is needed: `previous` cannot be negative (digits only), so this is >= 1.
    return max(previous + 1, history_spent)


def verdict_mismatch(verdict: Verdict | None, run_id: str, gate_ok: bool) -> str:
    """Why the persisted verdict is not the one this gate run produced; ``""`` if it is.

    The driver hands the generator a path to ``last_verdict.json`` and the ids it names.
    A missing record (the gate timed out, or crashed), a leftover record from an earlier
    run, or a record that disagrees with the exit code the gate just returned would all
    have the driver retry against facts that are not this run's — and a failing run whose
    verdict names nothing tells the generator "the gate failed; nothing failed". All four
    are ambiguous states, and an ambiguous state ends the run (N2).

    Args:
        verdict: the record read back after the gate, or ``None`` if unreadable.
        run_id: the receipt bundle the gate just wrote — the run this must describe.
        gate_ok: the gate's own exit status for that run.

    Returns:
        A human reason, or ``""`` when the verdict is this run's and is self-consistent.
    """
    if verdict is None:
        return f"no verdict was readable for run {run_id}"
    if verdict.run_id != run_id:
        return f"the verdict describes run {verdict.run_id!r}, not the run just made ({run_id!r})"
    if verdict.ok != gate_ok:
        return f"the verdict (ok={verdict.ok}) disagrees with the gate's exit (ok={gate_ok})"
    if not gate_ok and not failing_check_ids(verdict.checks):
        return f"the gate failed but the verdict names no failing check (run {run_id})"
    return ""
