"""Capability self-description: what borromeanRings IS, generated from what is on disk.

Every AI summary of this project lists six to eight quality gates. The real surface is
~30 checks across six governance matrices, ratchets, receipts, a ``noop`` status, portfolio
and effectiveness views, an adoption path and advisory lanes — and nothing presents it.
The README's own stated count drifted three times in one cycle.

This module renders the description from **sources of truth only** — the check registry
on disk, the spine, the ADR directory, the coverage map's matrix table — never from prose
that can rot. A script that declares nothing is reported as *undeclared*, never dropped:
silent omission is precisely the drift this exists to stop. See ADR-0052 and #132.

Pure: takes paths and text, returns data and text. ``describe.sh`` does the I/O.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

_LANES: tuple[str, ...] = ("shared", "python", "ci")
_ID_RE = re.compile(r'^id="([^"]+)"', re.MULTILINE)
_CMD_RE = re.compile(r'^cmd="([^"]*)"', re.MULTILINE)
_RUN_CHECK_RE = re.compile(r'run_check\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]*)"')
_MATRIX_ROW_RE = re.compile(r"^\|\s*\*\*([^*]+)\*\*\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)

_WORDS: dict[str, int] = {
    w: i
    for i, w in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
            "twenty",
        ]
    )
}
_TENS: dict[str, int] = {"twenty": 20, "thirty": 30, "forty": 40}


@dataclass(frozen=True)
class CheckInfo:
    """One check as the registry on disk describes it."""

    id: str
    enforces: str
    lane: str
    ratchet: bool


_HEADER_RE = re.compile(r"^#\s*(?:[0-9]{2}_[a-z_]+\s*[—-]+\s*)?(.+?)\s*$", re.MULTILINE)


def _header_comment(text: str) -> str:
    """The script's own one-line summary: the first comment after the shebang, with a
    leading ``NN_name —`` prefix stripped. Empty if the script has none."""
    for line in text.splitlines()[1:6]:
        if line.startswith("#") and line.strip("# ").strip():
            m = _HEADER_RE.match(line)
            return m.group(1) if m else line.lstrip("# ").strip()
        if line.strip() and not line.startswith("#"):
            break
    return ""


def _describe_script(path: Path, lane: str) -> CheckInfo:
    text = path.read_text(encoding="utf-8", errors="replace")
    cid = path.stem
    id_m, cmd_m = _ID_RE.search(text), _CMD_RE.search(text)
    if id_m and cmd_m:
        return CheckInfo(id_m.group(1), cmd_m.group(1), lane, "ratchet" in cmd_m.group(1).lower())
    header = _header_comment(text)
    run_m = _RUN_CHECK_RE.search(text)
    rid = run_m.group(1) if run_m else cid
    if header:
        return CheckInfo(rid, header, lane, "ratchet" in header.lower())
    if run_m and not run_m.group(3).startswith("$"):
        tool, command = run_m.group(2), run_m.group(3)
        return CheckInfo(rid, f"{tool}: {command}", lane, "ratchet" in command.lower())
    # Declared nothing. Say so rather than omit it: omission is the drift we are here to stop.
    return CheckInfo(cid, "undeclared (no id=/cmd=, no header comment, no run_check)", lane, False)


def discover_checks(checks_root: Path | str) -> list[CheckInfo]:
    """Every check script under the registry, in numeric order across lanes."""
    root = Path(checks_root)
    found: list[CheckInfo] = []
    for lane in _LANES:
        lane_dir = root / lane
        if not lane_dir.is_dir():
            continue
        for script in lane_dir.glob("[0-9]*.sh"):
            found.append(_describe_script(script, lane))
    return sorted(found, key=lambda c: c.id)


def matrices(coverage_map_text: str) -> list[tuple[str, str]]:
    """``(name, status)`` rows of the §6 governance-matrix table; ``[]`` if absent."""
    start = coverage_map_text.find("## 6.")
    if start < 0:
        return []
    end = coverage_map_text.find("\n## ", start + 1)
    section = coverage_map_text[start : end if end > 0 else None]
    return [(name.strip(), status.strip()) for name, status in _MATRIX_ROW_RE.findall(section)]


def number_word(word: str) -> int | None:
    """``"twenty"`` → 20, ``"thirty-two"`` → 32, unknown → ``None``."""
    w = word.strip().lower()
    if w in _WORDS:
        return _WORDS[w]
    tens, _, ones = w.partition("-")
    if tens in _TENS and ones in _WORDS and _WORDS[ones] < 10:
        return _TENS[tens] + _WORDS[ones]
    if w in _TENS:
        return _TENS[w]
    return None


def count_claims(readme_text: str) -> dict[str, int]:
    """Counts the README asserts: ``**N checks**`` and ``(<word> gates``. Absent ⇒ omitted."""
    claims: dict[str, int] = {}
    m = re.search(r"\*\*(\d+) checks\*\*", readme_text)
    if m:
        claims["checks"] = int(m.group(1))
    m = re.search(r"\(([a-z]+(?:-[a-z]+)?) gates", readme_text)
    if m:
        n = number_word(m.group(1))
        if n is not None:
            claims["gates"] = n
    return claims


def render_report(
    checks: Sequence[CheckInfo],
    *,
    required: Sequence[str],
    heavy: Sequence[str],
    adr_count: int,
    matrix_rows: Sequence[tuple[str, str]],
    commands: Sequence[str],
    skills: Sequence[str],
) -> str:
    """The capability report as Markdown. Every line traces to an input."""
    req, hvy = set(required), set(heavy)
    ratchets = [c.id for c in checks if c.ratchet]
    lines = [
        "# borromeanRings — capabilities (generated; do not edit)",
        "",
        f"**{len(checks)} checks** on disk · **{len(req)} required** on this repo · "
        f"{len(hvy)} heavy-lane · {len(ratchets)} threshold-free ratchets · "
        f"{adr_count} recorded decisions (ADRs)",
        "",
        "## Checks",
        "",
        "| Check | Lane | Enforces | Here |",
        "|---|---|---|---|",
    ]
    for c in checks:
        here = "required" if c.id in req else ("heavy" if c.id in hvy else "available")
        tag = " *(ratchet)*" if c.ratchet else ""
        lines.append(f"| `{c.id}` | {c.lane} | {c.enforces}{tag} | {here} |")
    lines += ["", "## Governance matrices", ""]
    lines += [f"- **{name}** — {status}" for name, status in matrix_rows] or ["- (none parsed)"]
    lines += ["", "## Commands", ""] + [f"- `{c}`" for c in commands]
    lines += ["", "## Skills (installed into governed projects)", ""] + [f"- `{s}`" for s in skills]
    lines += [
        "",
        "## Guarantees",
        "",
        "- **Fail-closed by allowlist**: only `pass`/`noop` are non-failing (ADR-0049).",
        "- **Honest about nothing**: a check that inspected nothing reports `noop`, never `pass`.",
        "- **Threshold-free**: ratchets are non-regression, never arbitrary targets.",
        "- **Tamper-evident receipts** per run, with a persisted verdict + history "
        "(ADR-0026/0046/0047).",
        "- **Governs by reference, per-project opt-in** (ADR-0013).",
        "",
    ]
    return "\n".join(lines)


def gather(home: Path | str, project: Path | str) -> dict[str, object]:
    """Every input the report needs, read once from disk (the only I/O in this module)."""
    import tomllib  # local: keeps the module importable where the report is not rendered

    home, project = Path(home), Path(project)
    checks = discover_checks(home / "checks")
    spine = project / "borromeanrings.toml"
    required: tuple[str, ...] = ()
    heavy: tuple[str, ...] = ()
    if spine.is_file():
        raw = tomllib.loads(spine.read_text(encoding="utf-8")).get("checks", {})
        required, heavy = tuple(raw.get("required", [])), tuple(raw.get("heavy", []))
    cov = home / "docs" / "ENFORCEMENT-COVERAGE.md"
    rows = matrices(cov.read_text(encoding="utf-8")) if cov.is_file() else []
    skills_dir = home / ".claude" / "skills"
    return {
        "checks": checks,
        "required": required,
        "heavy": heavy,
        "adr_count": len(list((home / "docs" / "adr").glob("0*.md"))),
        "matrix_rows": rows,
        "commands": sorted(p.name for p in home.glob("*.sh")),
        "skills": sorted(p.name for p in skills_dir.iterdir()) if skills_dir.is_dir() else [],
    }


BLOCK_BEGIN = "<!-- describe:begin -->"
BLOCK_END = "<!-- describe:end -->"


def summary_block(
    checks: Sequence[CheckInfo],
    *,
    required: Sequence[str],
    heavy: Sequence[str],
    matrix_rows: Sequence[tuple[str, str]],
) -> str:
    """The short generated summary the README carries between the describe markers.

    Kept to what a reader skims: the real counts (which the 04_self_description guard
    then holds the README to), the lanes, and the matrices — with a pointer to the full
    report. Deliberately not the whole table: that lives in ``describe.sh``'s output.
    """
    req = set(required)
    ratchets = sum(1 for c in checks if c.ratchet)
    lanes = {lane: sum(1 for c in checks if c.lane == lane) for lane in _LANES}
    lines = [
        BLOCK_BEGIN,
        f"**{len(checks)} checks** across three lanes — {lanes['shared']} shared, "
        f"{lanes['python']} Python, {lanes['ci']} heavy/CI — of which **{len(req)} are "
        f"required on this repo** and {ratchets} are threshold-free ratchets.",
        "",
        "Governance matrices: "
        + ", ".join(f"{name} ({status})" for name, status in matrix_rows)
        + ".",
        "",
        "Run `./describe.sh` for the generated report of every check, what it enforces, "
        "and where it applies. This block is generated; `04_self_description` fails the "
        "gate if the counts above stop matching the registry.",
        BLOCK_END,
    ]
    return "\n".join(lines)


def replace_block(readme_text: str, block: str) -> str:
    """``readme_text`` with the describe block replaced (or appended if absent).

    Everything outside the markers is preserved byte-for-byte: the generator owns only
    its own block, never the surrounding prose.
    """
    if not readme_text:
        return block + "\n"
    start, end = readme_text.find(BLOCK_BEGIN), readme_text.find(BLOCK_END)
    if start < 0 or end < 0 or end < start:
        sep = "" if readme_text.endswith("\n") else "\n"
        return readme_text + sep + "\n" + block + "\n"
    end += len(BLOCK_END)
    return readme_text[:start] + block + readme_text[end:]


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: print the capability report (Markdown, or ``--json``), or ``--readme`` to
    regenerate the README's describe block in place. Always exits 0."""
    import json
    import os
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    home = os.environ.get("BORROMEANRINGS_HOME") or str(Path(__file__).resolve().parents[2])
    project = (
        os.environ.get("BORROMEANRINGS_PROJECT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )
    data = gather(home, project)
    if "--readme" in args:
        # Rewrite (or append) the generated block in the PROJECT's README; the prose
        # around it is untouched. 04_self_description then holds the README to it.
        checks = data["checks"]
        if not isinstance(checks, list):  # pragma: no cover - gather() always returns a list
            raise TypeError("gather() returned a non-list 'checks' entry")
        readme = Path(project) / "README.md"
        current = readme.read_text(encoding="utf-8") if readme.is_file() else ""
        block = summary_block(
            checks,
            required=data["required"],  # type: ignore[arg-type]
            heavy=data["heavy"],  # type: ignore[arg-type]
            matrix_rows=data["matrix_rows"],  # type: ignore[arg-type]
        )
        readme.write_text(replace_block(current, block), encoding="utf-8")
        print(f"wrote the describe block in {readme}")
        return 0
    if "--json" in args:
        checks = data["checks"]
        if not isinstance(checks, list):  # pragma: no cover - gather() always returns a list
            raise TypeError("gather() returned a non-list 'checks' entry")
        out = {**data, "checks": [asdict(c) for c in checks]}
        print(json.dumps(out, indent=2))
    else:
        print(render_report(**data))  # type: ignore[arg-type]
    return 0
