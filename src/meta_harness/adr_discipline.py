"""ADR-discipline gate: a feature that changes source must document its decision.

borromeanRings records every load-bearing decision as an ADR (``docs/adr/NNNN-*.md``)
— but by *convention*, not enforcement (matrix rows D/H: "ADR present, not gated").
This closes that gap deterministically: on a branch whose name marks new work
(default prefix ``feat/``), a change that touches the source tree must also add or
modify an ADR, so the decision behind a new capability is never left undocumented.

Git-derivable and threshold-free (no arbitrary target — the no-absolute-target
principle): it asks only "did feature work touch source without recording a
decision?". Off unless ``13_adr`` is in ``[checks].required``. Pure logic here; the
check script supplies the branch name and the changed-path set from git. See
docs/specs/SPEC-adr-discipline.md and ADR-0043.
"""

from __future__ import annotations

from collections.abc import Sequence


def adr_violation(
    branch: str,
    changed_paths: Sequence[str],
    *,
    src_dir: str = "src",
    adr_dir: str = "docs/adr",
    require_prefixes: Sequence[str] = ("feat/",),
) -> str | None:
    """Return a violation message if this change needs an ADR but has none, else ``None``.

    Triggers only on a branch whose name starts with one of ``require_prefixes``
    (feature work). If any changed path is under ``src_dir`` and none is under
    ``adr_dir``, the decision behind the change is undocumented — a violation.
    Non-feature branches, doc-only changes, and any change that also touches an ADR
    all pass.
    """
    if not any(branch.startswith(prefix) for prefix in require_prefixes):
        return None
    src_prefix = src_dir.rstrip("/") + "/"
    adr_prefix = adr_dir.rstrip("/") + "/"
    touches_src = any(path.startswith(src_prefix) for path in changed_paths)
    touches_adr = any(path.startswith(adr_prefix) for path in changed_paths)
    if touches_src and not touches_adr:
        return (
            f"feature branch '{branch}' changes {src_dir}/ but records no decision — "
            f"add an ADR under {adr_dir}/ (e.g. {adr_dir}/NNNN-title.md) documenting why."
        )
    return None
