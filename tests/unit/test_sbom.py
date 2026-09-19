"""CycloneDX-shaped SBOM of the declared dependency closure (meta_harness.sbom). ADR-0061.

The shape is pinned exactly (bomFormat, specVersion, components[].name/version/purl) so
a consumer can rely on it; the closure walk is driven by an in-memory distribution map
so the test is deterministic and needs nothing installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meta_harness.sbom import (
    Component,
    Distribution,
    closure,
    declared_roots,
    installed_distributions,
    main,
    normalize_name,
    purl,
    render_sbom,
    sbom_document,
)

_PYPROJECT = """
[project]
name = "Demo_App"
version = "1.2.3"
dependencies = ["Requests>=2", "click ; python_version < '3.0'", "ghost>=1"]

[project.optional-dependencies]
dev = ["pytest>=8"]
"""

_INSTALLED = {
    "requests": Distribution("requests", "2.32.0", ("urllib3<3", "charset_normalizer<4")),
    "urllib3": Distribution("urllib3", "2.2.1", ("brotli; extra == 'brotli'",)),
    "charset-normalizer": Distribution("charset-normalizer", "3.3.2", ()),
    "pytest": Distribution("pytest", "8.3.0", ("pluggy<2", "colorama; sys_platform == 'win32'")),
    "pluggy": Distribution("pluggy", "1.5.0", ()),
}


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [("Requests", "requests"), ("charset_normalizer", "charset-normalizer"), ("a..b__c", "a-b-c")],
)
def test_normalize_name_pep503(raw: str, normalized: str) -> None:
    assert normalize_name(raw) == normalized


def test_purl_is_pypi_shaped_and_normalized() -> None:
    assert purl("Charset_Normalizer", "3.3.2") == "pkg:pypi/charset-normalizer@3.3.2"
    assert purl("pkg", None) == "pkg:pypi/pkg"


def test_declared_roots_runtime_only_by_default() -> None:
    runtime = ("Requests>=2", "click ; python_version < '3.0'", "ghost>=1")
    assert declared_roots(_PYPROJECT) == runtime
    assert declared_roots(_PYPROJECT, include_optional=True) == (*runtime, "pytest>=8")


def test_declared_roots_skips_unparseable_and_empty_manifests() -> None:
    assert declared_roots('[project]\nname = "x"\n') == ()
    assert declared_roots('[project]\ndependencies = [">=1", "ok==1"]\n') == ("ok==1",)


def test_closure_walks_installed_requires_and_reports_unresolved() -> None:
    components, unresolved, edges = closure(declared_roots(_PYPROJECT), _INSTALLED)
    assert components == (
        Component("charset-normalizer", "3.3.2", "pkg:pypi/charset-normalizer@3.3.2"),
        Component("requests", "2.32.0", "pkg:pypi/requests@2.32.0"),
        Component("urllib3", "2.2.1", "pkg:pypi/urllib3@2.2.1"),
    )
    # ghost has no marker and is not installed: unresolved (honest, not silently dropped).
    # click carries an environment marker and is absent: conditional, skipped silently.
    # brotli is an extra of urllib3 we did not ask for: not followed.
    assert unresolved == ("ghost",)
    assert edges == {
        "pkg:pypi/requests@2.32.0": (
            "pkg:pypi/charset-normalizer@3.3.2",
            "pkg:pypi/urllib3@2.2.1",
        ),
        "pkg:pypi/urllib3@2.2.1": (),
        "pkg:pypi/charset-normalizer@3.3.2": (),
    }


def test_closure_visits_each_distribution_once() -> None:
    installed = {
        "a": Distribution("a", "1", ("b", "c")),
        "b": Distribution("b", "1", ("c",)),
        "c": Distribution("c", "1", ("a",)),  # cycle
    }
    components, unresolved, _ = closure(("a",), installed)
    assert [c.name for c in components] == ["a", "b", "c"]
    assert unresolved == ()


def test_sbom_document_shape_is_cyclonedx() -> None:
    components = (Component("requests", "2.32.0", "pkg:pypi/requests@2.32.0"),)
    doc = sbom_document(
        "demo-app",
        "1.2.3",
        components,
        roots=("pkg:pypi/requests@2.32.0",),
        unresolved=("ghost",),
        edges={"pkg:pypi/requests@2.32.0": ()},
    )
    assert doc["bomFormat"] == "CycloneDX"
    assert doc["specVersion"] == "1.5"
    assert doc["version"] == 1
    assert doc["serialNumber"].startswith("urn:uuid:")
    assert doc["metadata"]["component"] == {
        "type": "application",
        "name": "demo-app",
        "version": "1.2.3",
        "purl": "pkg:pypi/demo-app@1.2.3",
        "bom-ref": "pkg:pypi/demo-app@1.2.3",
    }
    assert doc["components"] == [
        {
            "type": "library",
            "name": "requests",
            "version": "2.32.0",
            "purl": "pkg:pypi/requests@2.32.0",
            "bom-ref": "pkg:pypi/requests@2.32.0",
        }
    ]
    assert doc["dependencies"] == [
        {"ref": "pkg:pypi/demo-app@1.2.3", "dependsOn": ["pkg:pypi/requests@2.32.0"]},
        {"ref": "pkg:pypi/requests@2.32.0", "dependsOn": []},
    ]
    props = {p["name"]: p["value"] for p in doc["metadata"]["properties"]}
    assert props["borromeanrings:attestation"] == "none"
    assert props["borromeanrings:signed"] == "false"
    assert props["borromeanrings:unresolved"] == "ghost"


def test_sbom_document_is_deterministic_and_omits_unresolved_when_empty() -> None:
    args = ("demo", "1", (Component("a", "1", "pkg:pypi/a@1"),))
    one = sbom_document(*args, roots=(), unresolved=(), edges={})
    two = sbom_document(*args, roots=(), unresolved=(), edges={})
    assert one == two
    assert "timestamp" not in one["metadata"]
    names = [p["name"] for p in one["metadata"]["properties"]]
    assert "borromeanrings:unresolved" not in names
    # A different closure yields a different serial number.
    other = sbom_document(
        "demo", "1", (Component("b", "1", "pkg:pypi/b@1"),), roots=(), unresolved=(), edges={}
    )
    assert other["serialNumber"] != one["serialNumber"]


def test_render_sbom_end_to_end_from_pyproject_text() -> None:
    doc = render_sbom(_PYPROJECT, _INSTALLED, include_optional=True)
    assert doc["metadata"]["component"]["name"] == "demo-app"
    assert doc["metadata"]["component"]["version"] == "1.2.3"
    assert [c["name"] for c in doc["components"]] == [
        "charset-normalizer",
        "pluggy",
        "pytest",
        "requests",
        "urllib3",
    ]
    # Root edges: the application depends on the resolved declared roots (sorted).
    assert doc["dependencies"][0] == {
        "ref": "pkg:pypi/demo-app@1.2.3",
        "dependsOn": ["pkg:pypi/pytest@8.3.0", "pkg:pypi/requests@2.32.0"],
    }


def test_render_sbom_defaults_when_project_table_is_missing() -> None:
    doc = render_sbom("", {}, include_optional=False)
    assert doc["metadata"]["component"]["name"] == "unknown"
    assert doc["metadata"]["component"]["version"] == "0"
    assert doc["components"] == []


def test_installed_distributions_reads_the_live_environment() -> None:
    installed = installed_distributions()
    assert "pytest" in installed  # this test suite is running under it
    dist = installed["pytest"]
    assert dist.name == "pytest"
    assert dist.version
    assert all(isinstance(r, str) for r in dist.requires)


def test_main_writes_json_for_a_pyproject(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    assert main([str(tmp_path / "pyproject.toml"), "--optional"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["bomFormat"] == "CycloneDX"
    assert doc["metadata"]["component"]["name"] == "demo-app"
    assert any(c["name"] == "pytest" for c in doc["components"])


def test_main_out_flag_writes_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1"\n')
    out = tmp_path / "sbom.json"
    assert main([str(tmp_path / "pyproject.toml"), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["components"] == []
    assert capsys.readouterr().out == ""


def test_main_missing_manifest_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / "nope.toml")]) == 1
    assert "nope.toml" in capsys.readouterr().err


def test_main_rejects_unknown_flag(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--bogus"]) == 2
    assert "usage" in capsys.readouterr().err.lower()
