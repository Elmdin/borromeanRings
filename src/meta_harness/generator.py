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

from collections.abc import Mapping, Sequence
from pathlib import Path
from stat import S_ISREG

from meta_harness.verdict import is_failing

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


def snapshot_evidence(root: Path | str, *, exclude: Path | str | None = None) -> dict[str, str]:
    """Fingerprint every file under ``root``: ``{relative path: "<size>:<mtime_ns>"}``.

    Taken by the driver either side of the generator's run, over the gate's evidence
    area (``.meta-harness/``). Size *and* mtime, because resetting an attempt counter
    from ``2`` to ``0`` changes neither the file set nor the size.

    Args:
        root: directory to fingerprint; a missing one yields ``{}`` (a project that has
            never been gated has no evidence area, which is not a fault).
        exclude: one path to leave out — the driver's own capture of the generator's
            stdout, which it writes itself and which is therefore not a violation.

    Returns:
        A mapping suitable for :func:`evidence_writes`.
    """
    base = Path(root)
    skipped = Path(exclude).resolve() if exclude is not None else None
    snapshot: dict[str, str] = {}
    if not base.is_dir():
        return snapshot
    for path in base.rglob("*"):
        if skipped is not None and path.resolve() == skipped:
            continue
        try:
            info = path.stat()
        except OSError:
            continue  # unreadable now ⇒ it drops out, and dropping out reads as a write
        if not S_ISREG(info.st_mode):
            continue
        snapshot[str(path.relative_to(base))] = f"{info.st_size}:{info.st_mtime_ns}"
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
