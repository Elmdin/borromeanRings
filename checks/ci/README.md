# CI-tier "heavy" checks

Checks here run **only** under `verify.sh --heavy` (or `BORROMEANRINGS_HEAVY=1`) —
i.e. in CI, never on the fast inner Stop gate. They are for expensive analyses
(mutation testing, CVE/audit, license scans, secret-scan tools) that would make
the interactive gate too slow. A check here gates only when listed in
`[checks].heavy` **and** the run is `--heavy`. See ADR-0033.
