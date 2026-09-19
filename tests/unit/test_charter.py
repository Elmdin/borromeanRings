"""Session charter: parse, validate, render (docs/specs/SPEC-charter.md, ADR-0063).

Every validation rule has an exact-message test; the tier logic is checked in both
directions (high requires extras, low tolerates them); parsing fails closed on
unknown keys, wrong types, bad TOML and a missing file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meta_harness.charter import (
    Charter,
    CharterError,
    Violation,
    load_charter,
    missing_charter_reminder,
    parse_charter,
    render,
    validate,
)
from meta_harness.spine import Config

CFG = Config(required_checks=("22_charter",), context={}, charter_enabled=True)
LOW = (
    'goal = "Keep the gate honest."\nstakes = "low"\n'
    'done_when = ["verify.sh exits 0"]\nstop_when = ["a ratchet regresses"]\n'
    'may_not = ["push"]\nowner = "maintainer"\n'
)
HIGH = LOW.replace('"low"', '"high"') + (
    'rollback = "git revert"\nreviewer = "a human"\nblast_radius = "this repo"\n'
)


def _violations(text: str, config: Config = CFG) -> tuple[Violation, ...]:
    return validate(parse_charter(text), config)


def _fields(text: str, config: Config = CFG) -> list[str]:
    return [v.field for v in _violations(text, config)]


# --- parsing -----------------------------------------------------------------


def test_parse_low_charter() -> None:
    charter = parse_charter(LOW)
    assert charter.goal == "Keep the gate honest."
    assert charter.stakes == "low"
    assert charter.done_when == ("verify.sh exits 0",)
    assert charter.stop_when == ("a ratchet regresses",)
    assert charter.may_not == ("push",)
    assert charter.owner == "maintainer"
    assert charter.extras == {}


def test_parse_keeps_extras_as_strings() -> None:
    charter = parse_charter(HIGH)
    assert charter.extras == {
        "rollback": "git revert",
        "reviewer": "a human",
        "blast_radius": "this repo",
    }


def test_charter_is_frozen() -> None:
    charter = parse_charter(LOW)
    with pytest.raises(AttributeError):
        charter.goal = "x"  # type: ignore[misc]


def test_parse_missing_key_is_empty_not_error() -> None:
    charter = parse_charter('goal = "g"\n')
    assert charter.stakes == ""
    assert charter.done_when == ()
    assert charter.owner == ""


def test_parse_bad_toml_fails_closed() -> None:
    with pytest.raises(CharterError) as exc:
        parse_charter("goal = [\n")
    (v,) = exc.value.violations
    assert v.field == "file"
    assert v.reason.startswith("not valid TOML: ")


def test_parse_wrong_type_for_string_field() -> None:
    with pytest.raises(CharterError) as exc:
        parse_charter(LOW.replace('goal = "Keep the gate honest."', "goal = 3"))
    assert exc.value.violations == (Violation("goal", "must be a string, got int"),)


def test_parse_wrong_type_for_list_field() -> None:
    with pytest.raises(CharterError) as exc:
        parse_charter(LOW.replace('may_not = ["push"]', 'may_not = "push"'))
    assert exc.value.violations == (Violation("may_not", "must be a list of strings, got str"),)


def test_parse_non_string_list_item() -> None:
    with pytest.raises(CharterError) as exc:
        parse_charter(LOW.replace('may_not = ["push"]', "may_not = [1]"))
    assert exc.value.violations == (Violation("may_not[0]", "must be a string, got int"),)


def test_parse_non_string_extra() -> None:
    with pytest.raises(CharterError) as exc:
        parse_charter(LOW + "rollback = true\n")
    assert exc.value.violations == (Violation("rollback", "must be a string, got bool"),)


def test_parse_reports_every_type_error_at_once() -> None:
    with pytest.raises(CharterError) as exc:
        parse_charter('goal = 1\nowner = 2\ndone_when = "x"\n')
    assert [v.field for v in exc.value.violations] == ["done_when", "goal", "owner"]


def test_charter_error_message_lists_violations() -> None:
    err = CharterError((Violation("a", "r1"), Violation("b", "r2")))
    assert str(err) == "a — r1; b — r2"
    assert err.violations == (Violation("a", "r1"), Violation("b", "r2"))


def test_load_charter_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "CHARTER.toml"
    path.write_text(HIGH, encoding="utf-8")
    assert load_charter(path).stakes == "high"


def test_load_charter_missing_file_names_path(tmp_path: Path) -> None:
    path = tmp_path / "CHARTER.toml"
    with pytest.raises(CharterError) as exc:
        load_charter(path)
    assert exc.value.violations == (Violation("file", f"charter not found at {path}"),)


def test_load_charter_directory_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(CharterError) as exc:
        load_charter(tmp_path)  # a directory, not a file
    assert exc.value.violations == (Violation("file", f"charter not found at {tmp_path}"),)


def test_load_charter_unreadable_file_is_a_file_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "CHARTER.toml"
    path.write_text(LOW, encoding="utf-8")

    def _boom(self: Path, *args: object, **kwargs: object) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", _boom)
    with pytest.raises(CharterError) as exc:
        load_charter(path)
    assert exc.value.violations == (
        Violation("file", f"charter unreadable at {path}: permission denied"),
    )


# --- validation: each rule, exact message ------------------------------------


def test_valid_low_and_high_have_no_violations() -> None:
    assert _violations(LOW) == ()
    assert _violations(HIGH) == ()


@pytest.mark.parametrize("field", ["goal", "owner"])
@pytest.mark.parametrize(
    ("value", "reason"),
    [(None, "missing or empty"), ('""', "missing or empty"), ('"  \\t"', "whitespace only")],
)
def test_required_strings(field: str, value: str | None, reason: str) -> None:
    lines = [ln for ln in LOW.splitlines() if not ln.startswith(f"{field} =")]
    if value is not None:
        lines.append(f"{field} = {value}")
    assert _violations("\n".join(lines) + "\n") == (Violation(field, reason),)


def test_stakes_missing() -> None:
    text = LOW.replace('stakes = "low"\n', "")
    assert _violations(text) == (Violation("stakes", 'missing or empty; must be "low" or "high"'),)


@pytest.mark.parametrize("bad", ["medium", "LOW", " high "])
def test_stakes_unknown_value_is_never_coerced(bad: str) -> None:
    text = LOW.replace('stakes = "low"', f'stakes = "{bad}"')
    assert _violations(text) == (Violation("stakes", f'must be "low" or "high", got "{bad}"'),)


@pytest.mark.parametrize("field", ["done_when", "stop_when", "may_not"])
def test_required_lists_missing_and_empty(field: str) -> None:
    lines = [ln for ln in LOW.splitlines() if not ln.startswith(f"{field} =")]
    missing = "\n".join(lines) + "\n"
    assert _violations(missing) == (Violation(field, "missing or empty; list at least one item"),)
    empty = "\n".join(lines + [f"{field} = []"]) + "\n"
    assert _violations(empty) == (Violation(field, "missing or empty; list at least one item"),)


@pytest.mark.parametrize("field", ["done_when", "stop_when", "may_not"])
def test_blank_list_item_names_its_index(field: str) -> None:
    lines = [ln for ln in LOW.splitlines() if not ln.startswith(f"{field} =")]
    text = "\n".join(lines + [f'{field} = ["real item", "   ", ""]']) + "\n"
    assert _violations(text) == (
        Violation(f"{field}[1]", "whitespace only"),
        Violation(f"{field}[2]", "missing or empty"),
    )


@pytest.mark.parametrize(
    "item",
    [
        "it works",
        "Works",
        "done",
        "looks good.",
        "Good enough",
        "seems fine",
        "should work",
        "mostly done",
        "basically done",
        "the CLI probably exits 0",
        "Mostly green",
    ],
)
def test_done_when_hedge_is_not_a_predicate(item: str) -> None:
    text = LOW.replace('done_when = ["verify.sh exits 0"]', f'done_when = ["{item}"]')
    assert _violations(text) == (Violation("done_when[0]", f'hedge, not a predicate: "{item}"'),)


@pytest.mark.parametrize(
    "item", ["verify.sh exits 0", "the workaround is documented", "tests pass on CI"]
)
def test_done_when_predicate_with_no_hedge_passes(item: str) -> None:
    text = LOW.replace('done_when = ["verify.sh exits 0"]', f'done_when = ["{item}"]')
    assert _violations(text) == ()


def test_hedge_rule_applies_only_to_done_when() -> None:
    text = LOW.replace('stop_when = ["a ratchet regresses"]', 'stop_when = ["it works"]')
    assert _violations(text) == ()


def test_unknown_key_fails_closed() -> None:
    text = LOW + 'done_wen = "typo"\n'
    assert _violations(text) == (Violation("done_wen", "unknown key"),)


def test_unknown_key_with_non_string_value_fails_at_parse() -> None:
    with pytest.raises(CharterError) as exc:
        parse_charter(LOW + 'done_wen = ["typo"]\n')
    assert exc.value.violations == (Violation("done_wen", "must be a string, got list"),)


def test_high_requires_every_extra() -> None:
    text = LOW.replace('"low"', '"high"')
    assert _violations(text) == (
        Violation("blast_radius", 'required at stakes "high"; missing or empty'),
        Violation("reviewer", 'required at stakes "high"; missing or empty'),
        Violation("rollback", 'required at stakes "high"; missing or empty'),
    )


@pytest.mark.parametrize(
    ("value", "reason"), [('""', "missing or empty"), ('" "', "whitespace only")]
)
def test_high_extra_present_but_blank(value: str, reason: str) -> None:
    text = HIGH.replace('rollback = "git revert"', f"rollback = {value}")
    assert _violations(text) == (Violation("rollback", f'required at stakes "high"; {reason}'),)


def test_low_tolerates_extras() -> None:
    text = LOW + 'rollback = "git revert"\n'
    assert _violations(text) == ()


def test_high_stakes_fields_come_from_config() -> None:
    cfg = Config(
        required_checks=("22_charter",),
        context={},
        charter_enabled=True,
        charter_high_stakes_fields=("approver",),
    )
    text = LOW.replace('"low"', '"high"')
    assert _violations(text, cfg) == (
        Violation("approver", 'required at stakes "high"; missing or empty'),
    )
    # the default extras are now unknown keys under this config
    assert _fields(LOW + 'rollback = "x"\n', cfg) == ["rollback"]
    assert _violations(text + 'approver = "lead"\n', cfg) == ()


def test_unknown_stakes_does_not_also_demand_extras() -> None:
    text = LOW.replace('"low"', '"medium"')
    assert _fields(text) == ["stakes"]


def test_violations_are_reported_together_and_sorted() -> None:
    text = 'stakes = "high"\ndone_when = ["done"]\nmay_not = [""]\nbogus = "x"\n'
    fields = _fields(text)
    assert fields == sorted(fields)
    assert set(fields) == {
        "blast_radius",
        "bogus",
        "done_when[0]",
        "goal",
        "may_not[0]",
        "owner",
        "reviewer",
        "rollback",
        "stop_when",
    }


# --- render + reminder --------------------------------------------------------


def test_render_low() -> None:
    out = render(parse_charter(LOW))
    assert out == (
        "charter OK — stakes: low; owner: maintainer\n"
        "  goal: Keep the gate honest.\n"
        "  done_when: 1 predicate(s); stop_when: 1; may_not: 1"
    )


def test_render_high_lists_extras() -> None:
    out = render(parse_charter(HIGH))
    assert out.startswith("charter OK — stakes: high; owner: maintainer\n")
    assert out.endswith(
        "  done_when: 1 predicate(s); stop_when: 1; may_not: 1\n"
        "  blast_radius: this repo; reviewer: a human; rollback: git revert"
    )


def test_render_long_goal_is_truncated() -> None:
    long_goal = "x" * 200
    out = render(parse_charter(LOW.replace("Keep the gate honest.", long_goal)))
    assert "  goal: " + "x" * 117 + "…\n" in out


def test_reminder_is_one_short_line() -> None:
    line = missing_charter_reminder("CHARTER.toml")
    assert line == (
        "borromeanRings: [charter] is enabled but CHARTER.toml is missing — "
        "write it before governed work"
    )
    assert "\n" not in line
    assert len(line.encode("utf-8")) < 120


def test_reminder_names_the_configured_path() -> None:
    assert "docs/charter.toml is missing" in missing_charter_reminder("docs/charter.toml")


def test_charter_construct_directly() -> None:
    charter = Charter(
        goal="g", stakes="low", done_when=("p",), stop_when=("s",), may_not=("m",), owner="o"
    )
    assert charter.extras == {}
    assert validate(charter, CFG) == ()
