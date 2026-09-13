"""Where borromeanRings keeps state that the governed project must not be able to write.

Some of the harness's own records decide whether the gate runs at all: the retry
count (ADR-0079, #218) and the last-proven-green hash (#222). Kept inside the
governed tree, both are writable by the very agent they bound — and worse, both
are *computable*: the hashing is in this repository, so forging them needs no
secret, only the willingness to write one file.

They therefore live under ``$XDG_STATE_HOME/borromeanrings/<project digest>/``
(default ``$HOME/.local/state``), named by the project's resolved absolute path so
symlinked routes to one project share one record.

**What this buys, stated exactly.** It defeats an agent confined to the project
directory — the realistic one, and the one the local feedback loop exists for. It
is NOT a bound against intent: the gate runs the project's own test code as the
user, and that code can reach ``$HOME`` like any same-user process. A real bound
needs isolated execution (#144/#145). Never describe this as tamper-proof.

Pure path arithmetic; no I/O. Extracted from :mod:`meta_harness.retry_state`, which
still re-exports these names, so that :mod:`meta_harness.change_detect` can use the
same location without either module importing the other.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path

APP_DIR = "borromeanrings"
DIGEST_CHARS = 32  # must match retry_state: changing it would silently reset every count


class StateUnavailable(Exception):
    """State cannot be located, read or written. Every caller fails closed."""


def state_root(env: Mapping[str, str]) -> Path:
    """The XDG state base directory: ``$XDG_STATE_HOME`` or ``$HOME/.local/state``.

    A relative ``XDG_STATE_HOME`` is ignored, as the XDG Base Directory spec
    requires. Raises :class:`StateUnavailable` when neither yields an absolute
    path — never guesses a location, because a guess could land inside the tree
    and silently undo the whole point of this module.
    """
    xdg = env.get("XDG_STATE_HOME", "")
    if os.path.isabs(xdg):
        return Path(xdg)
    home = env.get("HOME", "")
    if os.path.isabs(home):
        return Path(home) / ".local" / "state"
    raise StateUnavailable("no absolute XDG_STATE_HOME or HOME to keep harness state under")


def project_digest(resolved_project: str) -> str:
    """Name a project by its resolved absolute path (symlinked routes share state)."""
    return hashlib.sha256(resolved_project.encode("utf-8", "surrogateescape")).hexdigest()[
        :DIGEST_CHARS
    ]


def project_state_dir(env: Mapping[str, str], resolved_project: str) -> Path:
    """``<state root>/borromeanrings/<project digest>`` — this project's state home."""
    return state_root(env) / APP_DIR / project_digest(resolved_project)
