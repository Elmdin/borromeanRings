"""The FAST (interactive) lane — which verification runs while you are still working.

borromeanRings ran one lane on every Stop: the whole required set, including the whole
test suite. On this repo that is 445 s of wall clock, 404 s of it ``40_test``, before the
agent may say it is finished (#226). The verification was not wrong, only mis-placed: a
full suite belongs on the pre-merge/CI path, where no one is waiting on it.

So there are three lanes, declared in config and never hardcoded:

``fast``
    The interactive lane the Stop hook runs (``verify.sh --fast``). Every required check
    runs; only ``40_test`` narrows, to the paths the project declares in
    ``[test].fast_paths``. A project that declares none has no fast lane and behaves
    exactly as it did before.
``full`` (the default)
    ``./verify.sh`` — every required check over everything.
``heavy``
    ``./verify.sh --heavy`` — full, plus the CI-tier checks (ADR-0033). ``--heavy``
    always implies the full lane; a "fast heavy" run would be a contradiction.

This module is the one place that knows what "fast" means, so the shell checks only ask
it a question. It is a leaf: it reads :class:`~meta_harness.spine.Config` and nothing else.

The honesty rule this module exists to keep: a fast-lane pass must never be readable as a
full-lane pass. :data:`FAST_LANE_NOTE` names what the lane did not run and where it is run
instead; it goes in the check's log, the receipt's ``summary``, and the gate's own output.
See ADR-0081 and docs/CHECKS.md.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Mapping, Sequence

from meta_harness.spine import Config

#: Environment variable ``verify.sh`` exports to tell every check which lane it is in.
LANE_ENV = "BORROMEANRINGS_LANE"
#: The interactive lane (``verify.sh --fast``).
FAST = "fast"
#: The default lane — everything, over everything.
FULL = "full"

#: What a fast-lane run did NOT verify, and where that verification still happens.
#: Printed wherever a fast-lane result is reported, so the partial verdict says so itself.
FAST_LANE_NOTE = (
    "FAST LANE: a partial run. Tests outside the declared fast paths were NOT run, "
    "and coverage was NOT measured, so the coverage ratchet did NOT gate this run. "
    "Both run in full on `verify.sh` (the full lane) and in CI before merge — "
    "a fast-lane pass is not a merge-worthy verdict. See ADR-0081."
)

#: A declared fast path must look like this: a relative POSIX path of plain segments.
#: Deliberately an allowlist — these strings reach a shell command line, and a config is
#: an input like any other (fail closed on anything surprising rather than quote harder).
_SAFE_PATH = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]*(?:/[A-Za-z0-9._][A-Za-z0-9._-]*)*")


def resolve_lane(args: Sequence[str], env: Mapping[str, str]) -> tuple[str, bool]:
    """The ``(lane, heavy)`` one gate invocation runs in, from its argv and environment.

    ``--heavy`` (or ``BORROMEANRINGS_HEAVY=1``) always wins: heavy IS the pre-merge lane,
    so ``--fast --heavy`` is a full heavy run, never a narrowed one — otherwise the one
    lane that blocks a merge could be told to skip most of the suite.
    """
    heavy = env.get("BORROMEANRINGS_HEAVY", "0") == "1" or "--heavy" in args
    lane = FAST if ("--fast" in args and not heavy) else FULL
    return lane, heavy


def effective_lane(config: Config, lane: str) -> str:
    """The lane to *report*: ``fast`` only when the fast lane actually narrowed something.

    ``--fast`` in a project that declared no ``[test].fast_paths`` ran everything, so
    calling that result partial would mislead as surely as calling a partial one complete.
    The label follows the verification that happened, not the flag that was typed.
    """
    return FAST if (lane == FAST and fast_test_paths(config, lane)) else FULL


def lane_from_env(env: Mapping[str, str]) -> str:
    """The lane this process is running in, read from the environment.

    Anything other than an exact ``fast`` is the full lane — an unset, misspelled, or
    forged value must never *narrow* verification. Fail-closed, in the safe direction.
    """
    return FAST if env.get(LANE_ENV, "") == FAST else FULL


def validate_fast_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """The declared fast paths, validated; raises :class:`ValueError` on anything unsafe.

    Rejects absolute paths, ``..`` traversal, and any character outside the allowlist,
    because these strings are interpolated into the shell command the check runs. A bad
    declaration is a hard error, never a silent fall-back to "run nothing".
    """
    clean: list[str] = []
    for raw in paths:
        path = raw.strip()
        if not path or not _SAFE_PATH.fullmatch(path) or ".." in path.split("/"):
            raise ValueError(
                f"borromeanrings.toml [test].fast_paths: {raw!r} is not a safe relative "
                "path (letters, digits, '.', '_', '-', '/'; no leading '/', no '..')."
            )
        clean.append(path)
    return tuple(clean)


def fast_test_paths(config: Config, lane: str) -> tuple[str, ...]:
    """The test paths to run in ``lane``, or ``()`` meaning "run the whole suite".

    ``()`` is returned for every lane but ``fast``, and for a ``fast`` run in a project
    that declared no ``[test].fast_paths`` — so not configuring anything changes nothing.
    """
    if lane != FAST:
        return ()
    return validate_fast_paths(config.test_fast_paths)


def fast_pytest_args(config: Config, lane: str) -> str:
    """The shell-quoted pytest path arguments for ``lane``, or ``""`` for the whole suite.

    The seam between this module and ``checks/python/40_test.sh``: the check runs the
    narrowed suite when this is non-empty and its unmodified full command when it is not.
    """
    return " ".join(shlex.quote(path) for path in fast_test_paths(config, lane))


def fast_lane_summary(paths: tuple[str, ...]) -> str:
    """The one-line receipt ``summary`` that marks a result as a fast-lane result.

    The gate prints a receipt's summary beside its status, so this is what stops a
    narrowed ``PASS`` from reading like a full one in the gate output.
    """
    return f"FAST LANE — only {', '.join(paths)}; full suite pre-merge"
