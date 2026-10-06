# D1d validation — October 5, 2026

**Partial: source acquisition/normalization passed; full-set bridge preview blocked.
No D1d publication acceptance.** See [D1D](../D1D.md) for exact scope and next blocker.

Baseline HEAD `16766b5c160c0bac370c1177387662646bf51b42`, D1c candidate SHA-256
`4bcfdc15e623939ebd9f485fec3f9fc5a31e5a1bcef93e26198d3f779c7b9fee`,
all 770 files matched before work. Existing source changes remain byte-identical
to that candidate. Only PM status, roadmap, history index and Desktop tracker
were intentionally updated among inherited files. No application implementation
change, owner-root access, commit, deployment or remote publication occurred.

| Check | Result | Evidence |
|---|---|---|
| Authorized acquisition | 19 consumed / 19 usable HTTP 200, zero retries, 2.302 s, 31,011 body bytes; budget closed | `evidence/d1d-20261005/attempt-ledger.json` |
| Metadata acceptance | Exact 18 returned IDs, 18 species, 13 Original 151, 18 provider descriptions ≤72, physical variant count unknown | `config/sealed/2026-10-05-det1/normalization.json` |
| Full bridge gate | Four canonical IDs above #251 rejected before preview journal/write | `evidence/d1d-20261005/bridge-gate.json` |
| Fresh synthetic rejection/restoration | Every table/photo/frozen goal unchanged; copied restoration exact; SQLite integrity OK | `evidence/d1d-20261005/synthetic-gate/preservation.json` |
| D1d verify/publication/idempotency/conflict/rollback/successor | **Not executed: first gate blocked** | Same preservation result |
| Focused importer/bridge/goals/reconciliation | **74 passed in 34.46 s**; includes earlier-data/synthetic workflow regressions, not D1d publication | `evidence/d1d-20261005/tests.txt` |
| Offline reproduction | D1d normalized package/gate and reconciliation match retained-byte reproduction | `evidence/d1d-20261005/reproduction.txt` |
| Original D1c reproduction | Passed, original inputs/derived outputs untouched | `evidence/d1d-20261005/d1c-preserved.txt` |
| Locked dependencies | Offline locked sync passed; 34 resolved / 32 audited | `evidence/d1d-20261005/dependencies.txt` |
| Python compilation | Passed (`src` and `scripts`) | `evidence/d1d-20261005/compile.txt` |
| JavaScript syntax | Every existing beta/web script passed | `evidence/d1d-20261005/javascript.txt` |
| Repository lint / format | Passed; 202 files already formatted | `evidence/d1d-20261005/lint.txt`, `format.txt` |
| Full suite / browser walkthrough | Not run: no application implementation or browser-visible behavior changed | Source preservation in final manifest |

Focused command:

```sh
uv run --no-sync pytest -q tests/test_d1d_metadata.py tests/test_sealed_catalog.py tests/test_sealed_expansion.py tests/test_broad_goals.py tests/test_filtered_goals.py tests/test_d1c_reconciliation.py
```

The final candidate lists inherited/new file SHA-256 values and retained source
hashes; its companion `candidate.sha256` binds the exact manifest. Files under
`evidence/d1d-20261005/validation-final/` record final inherited preservation.
The candidate excludes generated credentials and disposable databases. Private
raw evidence is pinned via inputs.json and the manifest; reproduction requires
those retained bytes. It does not authorize reacquisition.

Next: repair collection metadata/bridge support for canonical species above #251
while preserving goal policy and unknown physical attributes, then start a fresh
all-18 synthetic publication/successor rehearsal from the closed-budget retained
sources. Full all-era, variant/membership, PostgreSQL and beta/owner gates stay open.
