# B0 preservation and migration

B0 technical exit passed on September 27, 2026. Owner acceptance, accounts, live cutover and hosted-beta readiness are not established. The local app continues to use its original JSON and hunt database; no UI or live-store changes were made.

Private repository: https://github.com/dock108dev/dex. Baseline commit: `08aa5662088f326f86483b0fa4b2e026845316de`. The tested implementation commit is recorded in the private handoff and Git history, avoiding a self-referential commit hash in this document.

## What exists

`inventory.py` defines a versioned SQLite rehearsal schema: stable users, games, sets, printings, external mappings, physical copies, binders, import batches/records, owner-scoped hunt history and private archive evidence. IDs are deterministic UUIDs under a fixed namespace. Collector numbers remain text. Core inventory requires no species fields. An unprovisioned stable owner ID can later bind to an authenticated `admin` subject; no password, auth provider or session exists.

`migration.py` imports only the copied authoritative `config/pokedex_251.json`. Older ownership sources are retained as private evidence, never replayed as authority. Each owned record creates one copy; unowned records create none. Copy attributes retain null unknowns and exact money text; all original attributes also remain in reversible import records. Existing catalog source IDs map separately from internal IDs. Conflicting external mappings create visible issue records. A changed snapshot for an already-imported user is rejected for explicit reconciliation, not silently merged.

Edition unchecked means unresolved, not confirmed unlimited. First-edition checked is preserved. Finish/variant remain unresolved where legacy evidence cannot establish an exact printing. All 207 current copies retain some unresolved detail. B1/B2 must exclude those from exact variant completion/pricing until resolved. Shared inventory still includes ineligible Vintage 251 cards; the named, versioned Pokémon goal applies species eligibility separately. Goal management UI is B2.

The importer retains every snapshot file byte-for-byte in a private, owner-scoped archive, including source/provenance, settings, raw hunt evidence, assets and all three SQLite snapshots. Collection hunt rows additionally preserve their exact request/raw/coverage fields and sample/live labels. Snapshot databases use SQLite's backup API, retaining committed WAL data; restore never overwrites an existing directory. No backups or private inventory enter Git.

## Observed exit evidence

| Check | Result |
| --- | --- |
| Pre-change backup | 87 readable files; hashed manifest; 3 consistent SQLite backups |
| Authoritative source | 859 records; 207 owned; 133 Kanto / 20 Johto; 1 first-edition selection; no count drift |
| Exact comparison | Every source record and owned attribute matched; actual printing/copy projection matched Vintage 251 |
| Hunts | 2 saved searches with exact settings, raw evidence and sample/live labels; owner scoped |
| Repeat import | Identical full logical database, including IDs and mappings; no duplicates |
| Conflicts/uncertainty | 0 current identity conflicts; unresolved fields visible; synthetic conflict regression passes |
| Restore | All 87 archived files byte-equal; database integrity passes |
| Current app | Owner/config/UI hashes unchanged; live databases logically equal; restored collection/export/hunt reads pass |
| Tests | 100 passed; lint, formatting and JavaScript syntax checks required on final candidate |
| Fresh checkout | Uses empty catalog example and synthetic test ownership; private files not required |

SQLite backup changes physical database header bytes. Live preservation therefore compares complete logical database dumps; ordinary source files compare SHA-256. One existing FastAPI/Starlette TestClient deprecation warning remains; no runtime failure occurred.

## Reproduce locally

Keep all output outside the repository with restricted access. Commands assume a shell variable `B0_EVIDENCE` points to a new private directory under an owner-only parent. Snapshot creation is read-only, but a final cutover must pause writes and take a fresh consistent application-wide snapshot. This B0 run made no cutover.

```sh
uv run python scripts/snapshot_b0.py --source "$PWD" --output "$B0_EVIDENCE"
uv run python scripts/rehearse_b0.py \
  --snapshot "$B0_EVIDENCE/snapshot" --manifest "$B0_EVIDENCE/manifest.json" \
  --output "$B0_EVIDENCE/rehearsal"
uv run python scripts/verify_b0_source.py \
  --source "$PWD" --snapshot "$B0_EVIDENCE/snapshot" \
  --manifest "$B0_EVIDENCE/manifest.json" --restored "$B0_EVIDENCE/rehearsal/restored" \
  --report "$B0_EVIDENCE/source-check.json"
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
node --check web/app.js
```

The retained initial run uses `snapshot`, `manifest.json`, `rehearsal-final/report.json`, `rehearsal-final/inventory.db`, `rehearsal-final/restored` and `usability-and-unchanged.json` beneath the private evidence directory named in the handoff. Earlier rehearsal attempts remain retained. No owner-state differences were repaired by overwriting source.

## Limits and next stage

SQLite is a disposable B0 rehearsal target, not a hosted database selection. B1 must select a mature authentication component supporting the chosen login and recovery requirements, bind the existing stable owner ID through a controlled bootstrap, implement session-derived server authorization and prove two-user isolation with the second inventory empty. Do not expose today's unauthenticated local routes. Catalog/image/pricing redistribution rights, hosted operations and owner acceptance remain open gates. Future PostgreSQL migration must preserve these IDs and contracts.

At eventual authorized cutover: pause writes, take a final snapshot, reconcile changes since rehearsal, import/verify once, switch the authoritative store once, retain the original files and define export/replay of subsequent new writes before rollback. B0 restore reconstructs the legacy snapshot; it does not discard or translate future hosted writes automatically.
