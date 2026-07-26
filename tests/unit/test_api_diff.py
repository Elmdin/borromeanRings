"""Public-API breaking-change detection. ADR-0040."""

from meta_harness.api_diff import Signature, breaking_changes, public_api


def test_public_api_captures_signatures() -> None:
    src = "def f(a, b, c=1):\n    return a\n"
    api = public_api(src)
    assert api == {"f": Signature("function", ("a", "b", "c"), 2)}


def test_public_api_classes_and_methods_and_excludes_private() -> None:
    src = (
        "class C:\n"
        "    def m(self, x):\n"
        "        return x\n"
        "    def _hidden(self):\n"
        "        return 0\n"
        "def _priv():\n"
        "    return 1\n"
    )
    api = public_api(src)
    assert set(api) == {"C", "C.m"}
    assert api["C"].kind == "class"
    assert api["C.m"] == Signature("function", ("self", "x"), 2)


def test_public_api_varargs_and_kwonly() -> None:
    src = "def f(a, *args, k, **kw):\n    return a\n"
    api = public_api(src)
    assert api["f"].params == ("a", "*args", "k", "**kw")
    assert api["f"].required == 1  # only 'a' is a required positional


def test_removed_symbol_is_breaking() -> None:
    old = {"f": Signature("function", ("a",), 1)}
    assert breaking_changes(old, {}) == ["removed: f"]


def test_added_required_param_is_breaking() -> None:
    old = {"f": Signature("function", ("a",), 1)}
    new = {"f": Signature("function", ("a", "b"), 2)}
    assert breaking_changes(old, new) == ["f: added required parameter(s) (required 1 -> 2)"]


def test_removed_param_is_breaking() -> None:
    old = {"f": Signature("function", ("a", "b"), 2)}
    new = {"f": Signature("function", ("a",), 1)}
    out = breaking_changes(old, new)
    assert any("removed/renamed parameter(s): b" in x for x in out)


def test_kind_change_is_breaking() -> None:
    old = {"x": Signature("function", (), 0)}
    new = {"x": Signature("class", (), 0)}
    assert breaking_changes(old, new) == ["x: kind changed (function -> class)"]


def test_adding_optional_param_is_not_breaking() -> None:
    old = {"f": Signature("function", ("a",), 1)}
    new = {"f": Signature("function", ("a", "b"), 1)}  # b optional
    assert breaking_changes(old, new) == []


def test_new_symbol_is_not_breaking() -> None:
    assert breaking_changes({}, {"g": Signature("function", (), 0)}) == []
