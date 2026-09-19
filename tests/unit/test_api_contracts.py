"""API-usage contracts: deterministic, binary, AST-level rules (#130, ADR-0054)."""

from __future__ import annotations

from pathlib import Path

import pytest

from meta_harness.api_contracts import Rule, check_source, check_tree, load_pack, parse_rules

# --- parsing ------------------------------------------------------------------------------


def test_parse_rules_validates_kind_and_required_fields() -> None:
    rules = parse_rules(
        [
            {"kind": "banned", "symbol": "malloc"},
            {"kind": "forbidden_in", "symbol": "sleep", "within": "*_isr"},
            {"kind": "must_check", "symbol": "HAL_*_Init"},
            {"kind": "required_arg", "symbol": "open", "arg": "encoding"},
            {"kind": "paired", "symbol": "acquire", "pair": "release"},
            {"kind": "requires_before", "symbol": "read", "before": "init"},
        ]
    )
    assert [r.kind for r in rules] == [
        "banned",
        "forbidden_in",
        "must_check",
        "required_arg",
        "paired",
        "requires_before",
    ]
    assert isinstance(rules[0], Rule)
    with pytest.raises(ValueError, match="unknown rule kind"):
        parse_rules([{"kind": "vibes", "symbol": "x"}])
    with pytest.raises(ValueError, match="'within'"):
        parse_rules([{"kind": "forbidden_in", "symbol": "sleep"}])
    with pytest.raises(ValueError, match="'symbol'"):
        parse_rules([{"kind": "banned"}])


def test_rule_is_immutable() -> None:
    (rule,) = parse_rules([{"kind": "banned", "symbol": "malloc"}])
    with pytest.raises(AttributeError):
        rule.symbol = "free"  # type: ignore[misc]


# --- each rule kind: caught, compliant, counted ---------------------------------------------


def _one(kind: str, **fields: str) -> tuple[Rule, ...]:
    return parse_rules([{"kind": kind, **fields}])


def test_banned_catches_any_spelling_the_glob_covers() -> None:
    rules = _one("banned", symbol="*malloc", message="no heap in firmware")
    report = check_source("x = malloc(4)\ny = lib.malloc(8)\nz = calloc(1)\n", rules, "fw.py")
    assert [(v.path, v.line, v.rule.kind) for v in report.violations] == [
        ("fw.py", 1, "banned"),
        ("fw.py", 2, "banned"),
    ]
    assert report.violations[0].message == "no heap in firmware"
    assert report.references == 2


def test_forbidden_in_only_fires_inside_the_named_scope() -> None:
    rules = _one("forbidden_in", symbol="time.sleep", within="*_isr")
    src = "def tick_isr():\n    time.sleep(1)\n\ndef main():\n    time.sleep(1)\n"
    report = check_source(src, rules)
    assert [(v.line, v.rule.kind) for v in report.violations] == [(2, "forbidden_in")]
    assert report.references == 2  # both calls matched the symbol; one violated


def test_forbidden_in_async_scope_token_means_any_coroutine() -> None:
    rules = _one("forbidden_in", symbol="time.sleep", within="<async>")
    src = (
        "async def fetch():\n    time.sleep(1)\n\n"
        "def sync_helper():\n    time.sleep(1)\n\n"
        "class C:\n    async def m(self):\n        time.sleep(1)\n"
    )
    assert [v.line for v in check_source(src, rules).violations] == [2, 9]


def test_must_check_flags_a_discarded_result_only() -> None:
    rules = _one("must_check", symbol="HAL_*_Init")
    src = (
        "HAL_GPIO_Init(p)\n"
        "rc = HAL_UART_Init(u)\n"
        "if HAL_SPI_Init(s) != OK:\n    pass\n"
        "print(HAL_I2C_Init(i))\n"
    )
    report = check_source(src, rules)
    assert [v.line for v in report.violations] == [1]
    assert report.references == 4


def test_required_arg_needs_the_keyword() -> None:
    rules = _one("required_arg", symbol="open", arg="encoding")
    report = check_source('open(p)\nopen(p, "r")\nopen(p, encoding="utf-8")\n', rules)
    assert [v.line for v in report.violations] == [1, 2]
    assert "encoding" in report.violations[0].message


def test_paired_is_per_function_and_lexical() -> None:
    rules = _one("paired", symbol="lock.acquire", pair="lock.release")
    src = (
        "def good():\n    lock.acquire()\n    work()\n    lock.release()\n\n"
        "def bad():\n    lock.acquire()\n    work()\n\n"
        "def other():\n    lock.release()\n"
    )
    report = check_source(src, rules)
    assert [(v.line, v.rule.kind) for v in report.violations] == [(7, "paired")]
    assert report.references == 2


def test_requires_before_is_statement_ordered() -> None:
    rules = _one("requires_before", symbol="dev.read", before="dev.init")
    src = (
        "def good():\n    dev.init()\n    dev.read()\n\n"
        "def bad():\n    dev.read()\n    dev.init()\n\n"
        "def never():\n    dev.read()\n"
    )
    report = check_source(src, rules)
    assert [v.line for v in report.violations] == [6, 10]


def test_module_level_calls_count_for_banned_but_scope_rules_ignore_them() -> None:
    rules = parse_rules(
        [{"kind": "paired", "symbol": "a", "pair": "b"}, {"kind": "banned", "symbol": "c"}]
    )
    report = check_source("a()\nc()\n", rules)
    assert [v.rule.kind for v in report.violations] == ["banned"]
    assert report.references == 2


def test_unparseable_source_is_a_violation_not_a_pass() -> None:
    report = check_source("def (:\n", _one("banned", symbol="x"), "broken.py")
    assert [(v.rule.kind, v.path, v.line) for v in report.violations] == [
        ("syntax", "broken.py", 1)
    ]


def test_no_reference_means_zero_not_pass(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('hi')\n", encoding="utf-8")
    report = check_tree([tmp_path / "a.py"], _one("banned", symbol="malloc"))
    assert report.violations == () and report.references == 0


def test_check_tree_folds_files_and_keeps_paths(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("malloc(1)\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("x = 1\nmalloc(2)\n", encoding="utf-8")
    report = check_tree(sorted(tmp_path.glob("*.py")), _one("banned", symbol="malloc"))
    assert [(Path(v.path).name, v.line) for v in report.violations] == [("a.py", 1), ("b.py", 2)]
    assert report.references == 2


# --- packs: reusable rules with provenance ------------------------------------------------


def test_load_pack_requires_provenance_on_every_rule(tmp_path: Path) -> None:
    (tmp_path / "good.toml").write_text(
        '[[rules]]\nkind = "banned"\nsymbol = "x"\nsource = "https://docs/x"\n', encoding="utf-8"
    )
    (rule,) = load_pack("good", tmp_path)
    assert rule.source == "https://docs/x"
    (tmp_path / "folk.toml").write_text(
        '[[rules]]\nkind = "banned"\nsymbol = "x"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="source"):
        load_pack("folk", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_pack("missing", tmp_path)


def test_shipped_asyncio_pack_loads_and_cites_python_docs() -> None:
    rules = load_pack("python-asyncio")  # PACKS_DIR: shipped inside the package
    assert rules
    assert all(r.source.startswith("https://docs.python.org/") for r in rules)
    # the pack's headline rule: a fire-and-forget create_task is a real bug class
    report = check_source("asyncio.create_task(job())\n", rules)
    assert any(v.rule.kind == "must_check" for v in report.violations)


# --- AST corner cases: what a call "name" is, and where nested definitions live -----------


def test_calls_without_a_dotted_name_are_neither_matched_nor_counted() -> None:
    rules = _one("banned", symbol="*")
    # subscript / call-result / lambda targets have no dotted name: invisible to rules
    report = check_source("handlers[0]()\nmake()()\n(lambda: 1)()\n", rules)
    # only `make()` itself is a named call
    assert [v.line for v in report.violations] == [2]
    assert report.references == 1


def test_functions_nested_in_blocks_and_classes_are_still_scoped() -> None:
    rules = _one("forbidden_in", symbol="sleep", within="*_isr")
    src = (
        "if FLAG:\n"
        "    def tick_isr():\n        sleep(1)\n"
        "class Driver:\n"
        "    def rx_isr(self):\n        sleep(2)\n"
        "    def main(self):\n"
        "        def inner_isr():\n            sleep(3)\n"
        "        with ctx():\n"
        "            def late_isr():\n                sleep(4)\n"
    )
    report = check_source(src, rules)
    assert [v.line for v in report.violations] == [3, 6, 9, 12]


# --- PR #160 review: scopes are definitions, not names; no double counting; await ----------


def test_paired_does_not_let_one_class_satisfy_another_with_the_same_method_names() -> None:
    rules = _one("paired", symbol="self.open", pair="self.close")
    src = (
        "class A:\n    def run(self):\n        self.open()\n        self.close()\n\n"
        "class B:\n    def run(self):\n        self.open()\n"  # B.run never closes
    )
    report = check_source(src, rules)
    assert [v.line for v in report.violations] == [8]


def test_requires_before_is_scoped_to_the_definition_not_the_name() -> None:
    rules = _one("requires_before", symbol="dev.read", before="dev.init")
    src = "def go():\n    dev.init()\n\ndef go():\n    dev.read()\n"  # redefinition, same name
    assert [v.line for v in check_source(src, rules).violations] == [5]


def test_calls_in_defs_nested_in_blocks_are_counted_once_in_the_inner_scope() -> None:
    rules = _one("banned", symbol="sleep")
    src = (
        "if FLAG:\n    def tick():\n        sleep(1)\n"
        "    with ctx():\n        def late():\n            sleep(2)\n"
    )
    report = check_source(src, rules)
    assert report.references == 2
    assert [v.line for v in report.violations] == [3, 6]
    # and the inner scope owns them: forbidden_in on the inner names fires, on the outer not
    inner = _one("forbidden_in", symbol="sleep", within="tick")
    assert [v.line for v in check_source(src, inner).violations] == [3]


def test_must_check_sees_a_bare_await_as_discarded() -> None:
    rules = _one("must_check", symbol="fetch")
    src = (
        "async def main():\n    await fetch()\n    data = await fetch()\n"
        "    return await fetch()\n    await pending\n"  # a bare awaited NAME is not a call
    )
    assert [v.line for v in check_source(src, rules).violations] == [2]
