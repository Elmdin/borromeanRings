"""Suite-wide setup shared by every test.

The gate and the Stop hook keep state outside the governed tree, under
``$XDG_STATE_HOME/borromeanrings`` (ADR-0079, ADR-0082): the retry count and the
last-green record. Unisolated, every test that runs the gate writes that state into the
developer's real home, mixed in with the records of the projects they actually govern.
So the whole session gets a private ``XDG_STATE_HOME`` before any test runs; every
subprocess inherits it. Tests that need a specific state root still set their own.
See tests/integration/test_suite_state_isolation.py.
"""

import os
import shutil
import tempfile

_ORIGINAL = os.environ.get("XDG_STATE_HOME")


def pytest_configure(config: object) -> None:
    """Point every gate run in this session at a private state root.

    Created here, not at import, so merely importing this module (a collection-only
    run, a tool that loads conftest) leaves nothing behind.
    """
    os.environ["XDG_STATE_HOME"] = tempfile.mkdtemp(prefix="borromeanrings-test-state-")


def pytest_unconfigure(config: object) -> None:
    """Remove the session's state root and restore what the environment had."""
    shutil.rmtree(os.environ["XDG_STATE_HOME"], ignore_errors=True)
    if _ORIGINAL is None:
        os.environ.pop("XDG_STATE_HOME", None)
    else:
        os.environ["XDG_STATE_HOME"] = _ORIGINAL
