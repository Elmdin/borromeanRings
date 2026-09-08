"""The compaction brief: governance state that must survive context summarisation (#137).

When Claude Code compacts, whatever the model knew about the last gate verdict, the
obligations still open, and the identity policy is summarised away. The brief is the
short, evidence-backed text re-injected afterwards. Pure: facts in, text out.
"""

from __future__ import annotations

from pathlib import Path

from meta_harness.compaction_brief import gather_brief, render_brief
from meta_harness.status_assess import Enforcement, obligations
from meta_harness.verdict import Verdict


def test_obligations_name_failing_and_hollow_checks_only() -> None:
    v = Verdict(
        ok=False,
        checks=(("00_build", "pass"), ("13_adr", "fail"), ("17_prior_art", "noop"), ("x", "?")),
    )
    assert obligations(v) == [
        "13_adr: FAIL — fix before the next Stop gate",
        "x: ? — fix before the next Stop gate",
        "17_prior_art: inspected nothing (noop) — a green here proves less than it looks",
    ]


def test_obligations_empty_on_a_clean_pass_and_on_no_verdict() -> None:
    assert obligations(Verdict(ok=True, checks=(("00_build", "pass"),))) == []
    assert obligations(None) == []


def test_brief_states_verdict_obligations_enforcement_and_identity() -> None:
    text = render_brief(
        project="/home/u/proj",
        verdict=Verdict(ok=False, checks=(("13_adr", "fail"),), run_id="r9", harness_version="v1"),
        enforcement=Enforcement("auto", "4/4 hooks wired"),
        identity=("wimaan3", "dev@example.com"),
        harness_home="/opt/br",
    )
    assert text.startswith("borromeanRings context restored after compaction — proj")
    assert "Last gate: FAIL (run r9, borromeanRings v1)" in text
    assert "13_adr: FAIL — fix before the next Stop gate" in text
    assert "Enforcement: AUTO — 4/4 hooks wired" in text
    assert "Commit identity policy: wimaan3 <dev@example.com>; author overrides are blocked" in text
    assert "Re-gate: /opt/br/verify.sh" in text


def test_brief_is_honest_when_never_gated_and_no_identity() -> None:
    text = render_brief(
        project="/p",
        verdict=None,
        enforcement=Enforcement("manual", "no hooks"),
        identity=None,
        harness_home="/opt/br",
    )
    assert "Last gate: never run here" in text
    assert "Open obligations: none recorded" in text
    assert "identity policy" not in text.lower() or "no [git] identity declared" in text
    assert "⚠ Enforcement: MANUAL — no hooks" in text


def test_brief_is_short_enough_to_re_inject() -> None:
    many = tuple((f"{i:02d}_check", "fail") for i in range(40))
    text = render_brief(
        project="/p",
        verdict=Verdict(ok=False, checks=many),
        enforcement=Enforcement("auto", "ok"),
        identity=None,
        harness_home="/h",
    )
    assert len(text) < 2500
    assert "… and 30 more" in text


# --- the I/O edge: gather_brief reads the same evidence the self-status view reads ------


def test_gather_brief_reads_verdict_settings_and_identity(tmp_path: Path) -> None:
    from meta_harness.verdict import write_last_verdict

    (tmp_path / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["13_adr"]\n[git]\nname = "wimaan3"\nemail = "d@x"\n',
        encoding="utf-8",
    )
    write_last_verdict(tmp_path, Verdict(ok=False, checks=(("13_adr", "fail"),), run_id="r1"))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")
    text = gather_brief(tmp_path, "/opt/br")
    assert "Last gate: FAIL (run r1, borromeanRings unknown version)" in text
    assert "13_adr: FAIL" in text
    assert "wimaan3 <d@x>" in text
    # unreadable settings ⇒ reported as manual (no hooks), never as auto
    assert "Enforcement: MANUAL" in text
    assert "Re-gate: /opt/br/verify.sh" in text


def test_gather_brief_reads_wired_hooks_and_missing_identity(tmp_path: Path) -> None:
    (tmp_path / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["00_build"]\n', encoding="utf-8"
    )
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("[1, 2]", encoding="utf-8")  # not a dict
    text = gather_brief(tmp_path, "/h")
    assert "Last gate: never run here" in text
    assert "Commit identity: no [git] identity declared" in text
    assert "Enforcement: MANUAL" in text


# --- byte-exact renderings: every character of the brief traces to an input -------------


def test_brief_is_byte_exact_with_a_failing_verdict() -> None:
    text = render_brief(
        project="/home/u/proj/",
        verdict=Verdict(
            ok=False,
            checks=(("13_adr", "fail"), ("17_prior_art", "noop"), ("00_build", "pass")),
            run_id="r9",
            harness_version="v1",
        ),
        enforcement=Enforcement("partial", "2/6 hooks wired"),
        identity=("wimaan3", "dev@example.com"),
        harness_home="/opt/br",
    )
    assert text == "\n".join(
        [
            "borromeanRings context restored after compaction — proj",
            "",
            "Last gate: FAIL (run r9, borromeanRings v1)",
            "Open obligations:",
            "  - 13_adr: FAIL — fix before the next Stop gate",
            "  - 17_prior_art: inspected nothing (noop) — a green here proves less than it looks",
            "⚠ Enforcement: PARTIAL — 2/6 hooks wired",
            "Commit identity policy: wimaan3 <dev@example.com>; author overrides are blocked",
            "Re-gate: /opt/br/verify.sh",
        ]
    )


def test_brief_is_byte_exact_with_a_clean_pass_and_no_run_id() -> None:
    text = render_brief(
        project="proj",
        verdict=Verdict(ok=True, checks=(("00_build", "pass"),)),
        enforcement=Enforcement("auto", "6/6 hooks wired"),
        identity=None,
        harness_home="/h",
    )
    assert text == "\n".join(
        [
            "borromeanRings context restored after compaction — proj",
            "",
            "Last gate: PASS (borromeanRings unknown version)",
            "Open obligations: none recorded",
            "Enforcement: AUTO — 6/6 hooks wired",
            "Commit identity: no [git] identity declared",
            "Re-gate: /h/verify.sh",
        ]
    )


def test_brief_truncation_is_exact() -> None:
    many = tuple((f"{i:02d}_c", "fail") for i in range(12))
    text = render_brief(
        project="/p",
        verdict=Verdict(ok=False, checks=many),
        enforcement=Enforcement("auto", "ok"),
        identity=None,
        harness_home="/h",
    )
    lines = text.splitlines()
    assert lines[3] == "Open obligations:"
    assert lines[4] == "  - 00_c: FAIL — fix before the next Stop gate"
    assert lines[13] == "  - 09_c: FAIL — fix before the next Stop gate"
    assert lines[14] == "  … and 2 more (see .meta-harness/)"
    assert lines[15].startswith("Enforcement:")
    # exactly ten listed, never eleven
    assert sum(1 for line in lines if line.startswith("  - ")) == 10
    # exactly ten ⇒ no truncation line at all
    ten = render_brief(
        project="/p",
        verdict=Verdict(ok=False, checks=many[:10]),
        enforcement=Enforcement("auto", "ok"),
        identity=None,
        harness_home="/h",
    )
    assert "more" not in ten


def test_obligations_are_exact_and_ordered() -> None:
    v = Verdict(ok=False, checks=(("b", "noop"), ("a", "error"), ("c", "pass"), ("d", "fail")))
    assert obligations(v) == [
        "a: ERROR — fix before the next Stop gate",
        "d: FAIL — fix before the next Stop gate",
        "b: inspected nothing (noop) — a green here proves less than it looks",
    ]


def _settings(project: Path, payload: str) -> None:
    (project / ".claude").mkdir(exist_ok=True)
    (project / ".claude" / "settings.json").write_text(payload, encoding="utf-8")


def test_gather_brief_reports_auto_when_every_hook_is_wired(tmp_path: Path) -> None:
    import json

    from meta_harness.status_assess import HOOK_SCRIPTS

    (tmp_path / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["00_build"]\n', encoding="utf-8"
    )
    hooks = {
        event: [{"hooks": [{"type": "command", "command": f"/opt/br/.claude/hooks/{script}"}]}]
        for event, script in HOOK_SCRIPTS.items()
    }
    _settings(tmp_path, json.dumps({"hooks": hooks}))
    text = gather_brief(tmp_path, "/opt/br")
    n = len(HOOK_SCRIPTS)
    assert f"Enforcement: AUTO — {n}/{n} hooks wired to this borromeanRings" in text
    assert "⚠" not in text


def test_gather_brief_settings_edge_cases(tmp_path: Path) -> None:
    (tmp_path / "borromeanrings.toml").write_text(
        '[checks]\nrequired = ["00_build"]\n[git]\nname = "n"\n', encoding="utf-8"
    )
    # no settings file at all ⇒ the "no .claude/settings.json" wording, and a name
    # without an email is NOT an identity policy
    text = gather_brief(tmp_path, "/h")
    assert "⚠ Enforcement: MANUAL — no .claude/settings.json" in text
    assert "Commit identity: no [git] identity declared" in text
    # a valid but empty object ⇒ "no borromeanRings hooks wired"
    _settings(tmp_path, "{}")
    assert "no borromeanRings hooks wired" in gather_brief(tmp_path, "/h")
    # a JSON array is not settings ⇒ treated as absent
    _settings(tmp_path, "[]")
    assert "no .claude/settings.json" in gather_brief(tmp_path, "/h")
    # malformed ⇒ treated as absent
    _settings(tmp_path, "{oops")
    assert "no .claude/settings.json" in gather_brief(tmp_path, "/h")
