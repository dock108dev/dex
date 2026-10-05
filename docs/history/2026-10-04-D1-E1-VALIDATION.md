# D1/E1 local validation — October 4, 2026

Candidate: working tree based on HEAD
`fba1be13135b0b3bbb6cb674de5586e0f3c80740`. No new commit, push, hosted matrix,
Production eBay call or owner-installation migration was made. Existing October 4
documentation changes remain included. The final candidate's per-file SHA-256
manifest and complete review patch are private at:

- `/Users/michaelfuscoletti/dex-private/d1-e1-20261004/validation-final/candidate.json`
- `/Users/michaelfuscoletti/dex-private/d1-e1-20261004/validation-final/candidate.patch`

The candidate manifest covers modified and untracked non-ignored repository files
plus the Desktop `dex_next_steps.md` handoff. It is generated after documentation
closeout; its self hash is reported in chat, avoiding a circular documentation hash.
It does not read ignored private app files or credentials.

## Final required checks

| Check | Local result |
|---|---|
| `uv sync --locked --extra dev` | Pass; locked environment synchronized |
| `python -m compileall -q src` | Pass |
| `node --check` for all beta/static and web JavaScript | Pass |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass; 141 files |
| `pytest -q` | **434 passed**, 113.33 seconds, Python 3.14 |
| Final focused `tests/test_sealed_catalog.py` | **25 passed**, 4.40 seconds |
| Initial catalog/collection/migration focused group | **66 passed**, 26.26 seconds |
| `git diff --check` | Pass |
| Retained-source package reproduction | Byte-identical package and source-index output |
| Actual CLI published coverage report | Pass on final synthetic root |

The full suite reported one upstream Starlette/httpx deprecation warning. The
first full run passed 433 tests; final review then repaired chained rollback's
active-state comparison and added latest-observation qualification coverage.
The final full run above qualifies the repaired runtime. Earlier test-authoring
failures (a wrong goal-table name and import formatting) were repaired before
these final results; they were not product or source-access acceptance.

## Preserved copied state and imported real metadata

Final synthetic disposable root:
`/Users/michaelfuscoletti/dex-private/d1-e1-20261004/rehearsal-final`.
A fresh synthetic seed supplied two accounts and unrelated private state. The
rehearsal copied it before adding E1 and restored into an independent database.
All **38 existing tables**, excluding the intentionally appended catalog audit
journal, retained their exact row counts and value hashes. This includes **four
frozen goals**, copies, private photo bytes, two scan jobs, reservations, original
source archives, authentication and saved-state tables. No owner data or private
installation was used. Schema initialization was repeated; identical imports
returned the same ID. Publication, rollback and recovery preserved those hashes.

Retained evidence in `validation-final/`:
`preservation.json`, `review.json`, `coverage.json`, `coverage.txt`,
`before.copied.sqlite3` and `recovered.sqlite3`. Older rehearsal evidence is
preserved separately and does not qualify the repaired candidate.

Real-source package SHA-256:
`ec4c1f062ec822e44793de381390c626da4b8c59d0935879a52c5e6b74e85313`.
Normalized service fingerprint:
`71217d564211d72bb3d0851e1e2f32034733e1e5b2e2ec89d52bc15aebf82e71`.
Final published import ID: `34ae3a57-020a-4893-b431-b8af0a4eb2f3`.
The post-recovery journal uses package version `2026-10-04-v1-recovery-republish`;
records, observation dates and source meaning remain unchanged.

Published E1 counts: 28 sources; 1,025 species; 220 expansions (205 physical,
15 digital); one exact Scyther printing, booster membership, product, pack
relationship, offer and observation; zero normalized guaranteed inclusions; one
coverage manifest. Zero unresolved species mappings **among the one imported
printing**. There are 204 intended physical sets without E1 printings, one product
with unknown contents and one unknown seller/stock/price/shipping observation.
Zero guaranteed-card rows do not prove there are no guaranteed cards.

## Evidence classes and limits

Real official/provider/retailer responses support only the normalized facts and
explicit gaps in [the slice closeout](../D1_E1.md). Source URLs, times, raw hashes,
access-quality labels and normalized artifact hashes are versioned in
`config/sealed/2026-10-04/`. Raw restricted responses and sanitized denial summaries
remain in the private `source-evidence/` directory. Normalization is offline and
reproducible from those retained bytes.

Tests and copied-state rehearsal are automated synthetic account/state evidence;
synthetic stock/content test records do not prove live availability. The service's
verify transition checks structure/conflicts and does not manufacture independent
source review or Mike's approval. No owner, device, hosted PostgreSQL or new hosted
CI evidence was collected. Official set reconciliation, official product contents,
current purchasable stock, independent Scyther review, full all-era printings,
full-E1 corrective/integration work and E2–E6 remain open. Beta completion is not
claimed. The next finite D1/E1b scope is in the closeout and Desktop handoff.
