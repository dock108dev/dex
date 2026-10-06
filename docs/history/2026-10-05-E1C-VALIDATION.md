# E1c validation — October 5, 2026

**Locally qualified on generated synthetic SQLite.** [E1c](../E1C.md) records
catalog support, physical uncertainty, preserved policies, full-set publication and
ordinary browser evidence. Full all-era/beta/owner acceptance remains open.

Baseline HEAD `16766b5c160c0bac370c1177387662646bf51b42`; D1d manifest SHA-256
`ec03da0f17bdae012a9475a6974b345658070c91727b8b005fb09f0aa1686fd6`;
all 857 files matched before work. No owner-root access, acquisition, credentials
for any provider, purchase, hosting, deployment, commit or remote publication occurred.

| Gate | Result | Evidence |
|---|---|---|
| Baseline | Exact HEAD and 857 file hashes | `evidence/e1c-20261005/baseline.json` |
| Registry/catalog | Pinned 1,025 canonical identities; higher species supported; unsupported/malformed/category conflicts rejected | `canonical_species.py`, `tests/test_e1c.py` |
| Unknown physical fields | All 18 null edition/finish; SQL NULL and unresolved fields retained; export/import/serialization round-trip; known legacy compatibility | Full-set package and E1c regression tests |
| SQLite migration compatibility | No schema change needed; additive initializers repeated twice; exact rows/BLOB photo bytes | `migration.json` |
| Full publication | 18 exact preview/verify/publish; pre-review publish rejected; idempotency/conflicts; rollback and reviewed new-version restoration | `preview.json`, `publication.json`, `rollback.json` |
| Restoration | Copied baseline SQLite integrity OK and every row reproduced; two photo byte hashes exact | `publication.json`, private `before.sqlite3` / `restored.sqlite3` |
| Populated protection | 6 copies, hunt, research, binder, 5 goals, 2 jobs, 2 photos and consumed reservation populated before boundary; 39 identical tables, 16 intended catalog/journal changes | `preservation.json` |
| Goal policies | Vintage 251 and Original 151 frozen; old memberships unchanged; explicit 13-addition successor; five outside range excluded; no catalog-only progress gains | `successor-preview.json`, `successor-publication.json` |
| Ordinary browser | Full 18-card display; Morelull unknown edition/finish; explicit review/confirm; retained/reopened predecessor and successor; zero confirmed Packs coverage | `browser/*.png` / `*.txt` |
| Browser preservation | Existing protected rows/photos/journals exact; new goal/operation/generation and login bookkeeping classified | `browser-preservation.json` |
| Zero acquisition | Runtime 0; guarded server 0 across restarts | `acquisition-calls.json`, `browser/provider-calls.json` |
| Locked dependencies | Offline locked sync passed; 34 packages resolved / 32 audited | `dependencies.log` |
| Compilation/JavaScript | Python source/scripts compilation and all repository browser script syntax checks passed | `compile.log`, `required-checks.json` |
| Lint / format | Passed; 208 Python files already formatted | `lint-final.log`, `format-final.log` |
| Full suite on final app/test source | **527 passed in 176.63 seconds**, local Python 3.14 | `full-suite-final.log` |
| Retained-byte checks | E1c normalization/reconciliation and original D1c/D1d reconciliation pass | `normalization-check.log`, `reconciliation-check.log`, `d1c-check.log`, `d1d-check.log` |

One known dependency warning: Starlette deprecates the existing FastAPI test-client
httpx integration; no test failure or runtime acquisition followed. The earlier
full suite also passed (527 in 176.96 s), before the final legacy progress/display
compatibility checks. Only `full-suite-final.log` qualifies the final app/test source.
The accepted rehearsal root is `synthetic-r4`; three earlier harness failures are
retained and classified in `repair-history.json`. The first browser 500 exposed a
classic-projection compatibility gap; the fixed source was exercised through the
successful subsequent walkthrough, E1c regression and final full suite.

Final candidate: [manifest](../../evidence/e1c-20261005/validation-final/candidate.json)
and [SHA-256](../../evidence/e1c-20261005/validation-final/candidate.sha256).
The manifest includes inherited files plus E1c source, package, evidence, docs and
Desktop tracker; intentional inherited changes are listed separately. Original
D1d rejected input, failed-preview evidence and normalization/reconciliation bytes
remain pinned to their historical candidate.

**Remaining blocker:** official Detective Pikachu booster/promo/deck applicability
for all 18 relationships. All-era coverage, PostgreSQL execution, real offers/eBay
and full beta/owner acceptance remain open.
