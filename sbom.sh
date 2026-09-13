#!/usr/bin/env bash
# borromeanRings — SBOM (software bill of materials).
#
# Emits a CycloneDX 1.5 JSON inventory of the project's declared dependency closure —
# name, version, purl and the dependency graph per component — from nothing but the
# Python stdlib (tomllib + importlib.metadata). No network, no new dependency, no
# external tool. It describes the closure AS INSTALLED in the current environment (run
# it where `pip install -e ".[dev]"` ran, e.g. CI); requirements it cannot resolve are
# listed under metadata.properties `borromeanrings:unresolved`, never dropped silently.
# NOT signed or attested — see ADR-0061 for the maintainer-deferred provenance items.
# Deterministic: no timestamp; the serial number derives from the closure.
#
# Usage: ./sbom.sh [MANIFEST=pyproject.toml] [--optional] [--out FILE]
#   --optional   include [project.optional-dependencies] groups in the closure
#   --out FILE   write the document to FILE instead of stdout
set -uo pipefail

BORROMEANRINGS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BORROMEANRINGS_HOME
PYTHONPATH="$BORROMEANRINGS_HOME/src" python3 -c \
  'import sys; from meta_harness.sbom import main; sys.exit(main(sys.argv[1:]))' "$@"
