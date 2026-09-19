# ADR-0084 — `init.sh` makes a repository, so `12_secrets` can be a default

**Status:** Accepted · 2026-09-19 · issue #236 (split out of #230) ·
**Relates to:** ADR-0049 (honest `noop`), ADR-0042 (`12_secrets` fails closed outside git),
#186 (a check that cannot list its inputs must fail, never `noop`)

## Context

`12_secrets` belongs in the required set every new project gets from `init.sh`. It is not
a ratchet: it has no baseline to seed and no threshold to meet, so the "start green"
reasoning that keeps `[hygiene].requires` empty does not apply. It fires only when a real
credential is in the tree. Leaving it out traded no friction for no protection, and a
freshly initialised project gated no secrets at all.

Adding it broke `init.sh`'s own acceptance, that a fresh project gates green, because
`12_secrets` fails closed when the project is not a git repository: without git there is
no tracked-file set, and an empty scan must never read as a clean one. Both sides were
right, which made this a decision rather than a bug.

Building the fix exposed two more ways the check could pass without looking:

- `git ls-files … || true` swallowed a failed enumeration (a corrupt index, say),
  scanned an empty list and reported `pass`.
- A repository that tracks nothing yet also scanned an empty list and reported `pass`,
  where ADR-0049 requires `noop`.

## Decision

1. **`init.sh` runs `git init` when the target is not already inside a repository, and
   says so.** An existing repository is left exactly as it is. Nearly every check here
   assumes version control (branch policy, commit discipline, identity, provenance, secret
   scanning), and `git init` is the ordinary first step of a new project. So a new
   project gets a repository rather than a gate that starts red.
2. **`12_secrets` joins the default required set.**
3. **`12_secrets` never passes without looking:** a failed `git ls-files` fails closed with
   git's error in the log, and an empty tracked set is `noop` ("no tracked files: nothing
   to scan yet"). A fresh project therefore gates green *honestly*, with `12_secrets`
   counted among the checks that inspected nothing until something is committed.
   The PR's security review found two more routes, both closed before merge: a tracked
   file that exists but cannot be read was skipped silently (it now fails closed, named),
   and inherited `GIT_DIR` / `GIT_WORK_TREE` overrode `git -C` so the scan read a decoy
   repository (`verify.sh` now unsets them, and the `GIT_CONFIG*` injection variables,
   for every check). A second pass found a third: a `.git` *file* pointing at another
   repository listed paths none of which exist here, so nothing was read. When every
   tracked file is absent from the working tree, the index does not describe this
   directory, and the check now fails closed.

   **The boundary, stated:** a decoy crafted to share this project's filenames is
   intent-level forgery by something that controls the project directory. The README's
   trust boundary excludes exactly that (the gate resists accident and naive forgery, not
   a hostile agent; #144, #145), so it is out of scope here rather than unconsidered.

## Alternatives considered

- **`noop` when the project is not a git repository at all.** Rejected. It turns a
  visible failure into a silent non-scan, which is the exact shape that let the gap in
  #230 survive. A project without version control would never have its secrets scanned,
  and nothing would say so beyond a hollow count.
- **Scan the working tree when there is no index.** Rejected for now. The working tree
  is what pulled borromeanRings' own receipt logs into the scan in #219, and a non-git
  project has no ignore semantics to lean on. It would need its own design.
- **`init.sh` refuses a non-git target.** Considered, and close. It is equally honest,
  but it adds a step for every new project to fix a premise (no version control) that
  `init.sh` can fix itself. It would also have required changing the existing acceptance
  test to accommodate the feature, which the issue rightly treated with suspicion.
  Running `git init`, and saying so, keeps that test's premise (a bare directory gates
  green) true without weakening what it asserts.

## Consequences

- (+) Every new project gates secrets from its first run.
- (+) Every route to a vacuous `pass` that the build and its review found is closed:
  can't enumerate ⇒ `fail`; can't read a tracked file ⇒ `fail`; nothing to read ⇒ `noop`;
  the environment cannot redirect which repository is read. "No route we know of" is the
  claim; the review is why the list is longer than the first draft's.
- (−) `init.sh` now writes a `.git` directory into a bare target. It is announced, and
  it is what a new project needs anyway, but it is a new side effect.
- (−) Until the first commit, a fresh project's `12_secrets` is `noop`, and the hollow
  count grows by one. That is the honest state; the demo's step 2 now reads `5 of 8`.
