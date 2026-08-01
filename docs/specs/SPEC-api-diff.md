# SPEC — Public-API breaking-change detection

**Status:** Implemented · **Realized by:** `src/meta_harness/api_diff.py`,
`checks/python/34_api_diff.sh`, `[api]` · ADR-0040

## Contract

`34_api_diff` compares the public surface of `src` against the **merge-base** with
the integration branch and fails on backwards-incompatible changes.

| Change | Breaking? |
|---|---|
| removed public function/class/method | yes |
| removed / renamed parameter | yes |
| new **required** parameter | yes |
| function ↔ class kind change | yes |
| added **optional** parameter | no |
| new public symbol | no |

- **Policy:** breaks fail unless `[api].allow_breaking = true` (a deliberate
  major-version release). No base to diff (first commit / detached HEAD) ⇒ pass.
- **Native + portable:** stdlib `ast` for signatures; git `<rev>:./<path>` for the
  prior version (works whether the project is a git root or a subdirectory).
- **Justified for libraries** — enabled on `examples/textkit`, not the meta-harness
  (which has no external API consumers). See ADR-0039/0040.

Pure `public_api` / `breaking_changes` (100% covered). Adversarially verified:
adding a required param to `textkit.slugify` fails the gate; reverting passes.
