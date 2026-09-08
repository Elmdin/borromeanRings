# SPEC — Verdict evidence, intent and risk band

**Status:** Implemented · **Realized by:** `src/meta_harness/evidence.py`,
`src/meta_harness/verdict.py` (`risk_band`, extended `Verdict`), `verify.sh` (verdict
block), `src/meta_harness/status_assess.py` (`evidence_lines`),
`src/meta_harness/ledger.py` (`evidenced`) · ADR-0056 · Issue #134

## 1. Problem

The persisted verdict (ADR-0046) says *that* the gate was satisfied — `ok`, plus a status
per check. It does not say **what was shown to happen**: which command ran, how it exited,
where its log is, what the receipt's tamper-evident hash was, which branch and commit
were under review. A reviewer who wants to trust a green must open the receipt bundle by
hand. ADR-0049 made "inspected nothing" visible; this makes "what was shown" visible, and
turns those facts into a **categorical** band that says where human attention belongs.

## 2. Goals

- **G1** Every verdict carries per-check **evidence**: the receipt's command, exit code,
  log path + size, content hash, and which lane (fast / heavy) required it.
- **G2** Every verdict carries the gated **intent**: branch, head SHA, and the
  gated-input digest (the same fingerprint the no-op Stop skip trusts).
- **G3** A **risk band** derived deterministically from the recorded statuses. Categorical
  (`green` / `hollow` / `red`), never a numeric score, never a threshold.
- **G4** Back-compatible: records written before this parse unchanged with empty defaults;
  a missing band is reported as *not recorded*, never re-derived into a claim.
- **G5** Surfaced where verdicts are read: the gate output, self-status, and the ledger.

## 3. Non-goals

- The band **never relaxes a gate.** `ok` is computed exactly as before (fail-closed by
  allowlist, ADR-0049); the band is derived *after* and only reported.
- No new receipt fields. Evidence is lifted from what `_lib.sh` already writes.
- Touched-area bands from `CODEOWNERS` groupings and a `merge.sh` evidence requirement
  (both named in #134) are **deferred** — see ADR-0056 §Deferred.

## 4. Contract

### 4.1 Record shape (`.meta-harness/last_verdict.json`, and one line each in
`verdict_history.jsonl`)

```json
{
  "ok": true,
  "run_id": "20260908T101500Z-4242",
  "digest": "<sha256 over intact receipt hashes>",
  "harness_version": "v0.1.0-12-gabc1234",
  "risk": "hollow",
  "intent": {
    "branch": "feat/verdict-evidence",
    "head_sha": "0123456789abcdef0123456789abcdef01234567",
    "input_digest": "<sha256 of the gated inputs — change_detect.compute_state_hash>"
  },
  "checks": [["00_build", "pass"], ["60_mutation", "noop"]],
  "evidence": [
    {
      "check": "00_build",
      "command": "python -m build",
      "exit_code": 0,
      "log": "/proj/.meta-harness/receipts/<run>/00_build.log",
      "log_bytes": 812,
      "content_sha256": "<receipt hash>",
      "lane": "fast"
    },
    {
      "check": "60_mutation",
      "command": "mutmut run (mutation-score ratchet vs baseline)",
      "exit_code": 0,
      "log": "/proj/.meta-harness/receipts/<run>/60_mutation.log",
      "log_bytes": 0,
      "content_sha256": "<receipt hash>",
      "lane": "heavy"
    }
  ]
}
```

New fields: `risk`, `intent`, `evidence`. Everything else is unchanged (ADR-0046/0048).

### 4.2 Evidence (`evidence.py`)

| Field | Source | Default when absent |
|---|---|---|
| `check` | receipt `check` | — (an entry without a string `check` is dropped) |
| `command` | receipt `command` | `""` |
| `exit_code` | receipt `exit_code` | **`-1`** (`EXIT_NOT_RECORDED`) — an absent or non-integer exit must never read as `0` |
| `log` | receipt `log` | `""` |
| `log_bytes` | `os.path.getsize(log)` at verdict time | `0` (missing log) |
| `content_sha256` | receipt `content_sha256` | `""` |
| `lane` | `"heavy"` iff the check is in `[checks].heavy`, else `"fast"` | `"fast"` |

Only **intact** required receipts become evidence — a `MISSING` or `!TAMPERED` row has no
evidence entry (there is nothing trustworthy to cite), and the row itself bands red.
Check-specific extras (coverage %, worst function, …) stay in the receipt.

### 4.3 Intent (`evidence.py`)

`read_intent(project_root, input_digest)` runs `git rev-parse --abbrev-ref HEAD` and
`git rev-parse HEAD` with a **fixed argv, no shell** (`# nosec B603 B607`, the same pattern
as `status.py`). Outside a repo, or with git absent, both are `""`; the digest is kept.
`input_digest` is `change_detect.compute_state_hash(project_root, config)` — `""` on an
`OSError`, never a failed gate.

### 4.4 Risk band (`verdict.risk_band`)

Precedence **red > hollow > green**, decided from the recorded `(check, status)` pairs
only:

| Condition | Band |
|---|---|
| any status `is_failing()` (fail, error, missing, tampered, or *unknown*) | `red` |
| otherwise, any status `noop` — **or no checks at all** | `hollow` |
| otherwise | `green` |

Unknown statuses band red because the classifier is the same allowlist the gate uses
(ADR-0049). An empty check set is hollow: "nothing looked" cannot be green. The gate
prints one line: `risk-band: HOLLOW · evidence: 19 receipt(s)`.

### 4.5 Surfaces

- **Self-status** (`status.sh`): `Risk band:    GREEN · evidence: 19 receipt(s) recorded
  (4 heavy-lane)` and `Intent:       feat/x @ 0123456789ab` (branch and/or 12-char SHA,
  omitted entirely when nothing was recorded). A pre-evidence record renders
  `Risk band:    not recorded (verdict predates evidence capture)`.
- **Ledger** (`ledger.sh`): a new `EVIDENCE` column (`evidenced/runs`, `—` when never
  gated) and `… · N with evidence` in the tally.

## 5. Edge cases

| Case | Required behaviour |
|---|---|
| Old record (no `risk`/`intent`/`evidence`) | parses; `risk == ""`, `intent == Intent()`, `evidence == ()` |
| `risk` is not a string | coerced with `str()` — the record is kept, never dropped |
| `intent` is not an object / `evidence` is not a list | empty defaults |
| evidence entry is not an object, or `check` is not a string | that entry is skipped, siblings kept |
| `exit_code` / `log_bytes` are non-integers (incl. JSON `true`) | `-1` / `0` — `bool` is explicitly not an int here |
| required receipt missing or tampered | row bands red; no evidence entry for it |
| git absent / not a repo | intent branch + SHA `""`; gate outcome unaffected |
| verdict write fails | best-effort as before — a real PASS is never turned into a FAIL |

## 6. Verification

- `tests/unit/test_evidence.py` — exact-value construction from receipts, `to_dict` /
  parse round trip, every malformed shape above, real-git and no-git intent reads.
- `tests/unit/test_verdict.py` — exact `to_dict` of a rich verdict, file + history round
  trip, old-record defaults, malformed nested fields, every `risk_band` branch.
- `tests/unit/test_self_status.py`, `tests/unit/test_ledger.py` — exact rendered lines.
- `tests/integration/test_harness_version_stamp.py` — the real gate on
  `examples/textkit`: evidence matches each receipt hash-for-hash, the band is printed and
  re-derivable from the record, intent matches `git rev-parse HEAD`.
