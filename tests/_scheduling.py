"""Which tests may run beside which, when the suite runs in parallel (#253, ADR-0086).

Test support, not harness code: it decides only how work is handed to workers.

Two rules, and the second is the one that matters:

1. **A file's tests stay together.** Most integration tests here build a fixture project
   and gate it through a module-scoped fixture; splitting a file across workers would
   rebuild that fixture per worker and pay for the parallelism twice.
2. **Files that share a resource declare it.** `tests/integration/test_example_governed.py`
   and `test_harness_version_stamp.py` both run the real gate against the *same*
   in-repo project, `examples/textkit`, and then read "the newest run directory" out of
   it. Run side by side, each can read the other's run: observed, not theorised — both
   files failed exactly that way the first time the suite was run in parallel. They
   declare one group, so one worker runs both.

A module opts into a shared group with a module-level ``XDIST_GROUP = "<name>"``.
"""

from __future__ import annotations

#: The attribute a test module sets to join a shared group.
GROUP_ATTRIBUTE = "XDIST_GROUP"


def group_for(module_id: str, declared: object = None) -> str:
    """The scheduling group of a test module: what it declared, else the module itself.

    ``declared`` is whatever the module's ``XDIST_GROUP`` holds — anything that is not a
    non-empty string is ignored, so a typo degrades to per-file scheduling (the safe
    default) instead of silently grouping everything under one name.
    """
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    return module_id
