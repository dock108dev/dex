# E5a — saved Packs research using retained data

October 5, 2026. Local synthetic qualification is recorded in
[the validation record](history/2026-10-05-E5A-VALIDATION.md). E5a completes the
retained-data save/reopen loop. E4 refresh, live availability and full E5 remain open.

Open **Packs to open** from a frozen Original 151 goal. Choose the whole goal or
missing species and an optional expansion filter, then **Save research**. An
optional name defaults to the goal name, retained version and selected species.
**Saved Packs research** is accessible from collection/goals navigation and every
Packs page. Reopen, rename and remove operate only on the signed-in account's item.
Renaming leaves its saved content intact; removing deletes only that research row.

Each item holds a server-generated, hash-checked snapshot: frozen goal ID/version,
lineage and eligibility, full reviewed catalog provenance, account progress at save
time, scope and local filters, exact printing/expansion/product identities, product
relationships, unresolved memberships, immutable observation IDs and checked times,
source hashes and uncertainty. Clients submit scope and name, never a result
snapshot, observation list or account identity. The server validates the exact goal
version, account access, missing-species scope and compatible expansion filter.
POST actions use existing authentication and CSRF middleware.

Reopening displays the saved scope without recomputing current ownership or choosing
a successor. It checks current reference availability solely to flag gaps; missing,
archived or changed records do not replace the snapshot or break the item. Goal and
catalog-journal gaps are explicit too. Links into classic eBay retain the selected
goal ID. Reopened pages have no filter/navigation action that silently expands the
saved scope. A different scope can be saved from its live retained-data Packs view.

The research saved date is separate from every original source checked time.
The 24-hour freshness label ages against that original time on reopening; stored
observations never refresh. Neither saving nor a fresh-age label establishes stock.
Official contents, quantities, guaranteed inclusions, actual seller and shipping
remain unknown wherever unresolved. Scyther expansion membership does not establish
Bundle contents or pull odds. Public sealed metadata remains separate from private
`saved_pack_research` rows; no ownership, goal, hunt or reservation mutation is made.

## Additive migration and reproduction

The repeatable feature DDL works with the repository's SQLite/PostgreSQL service
pattern. Existing local collection roots require an explicit operator migration:

```sh
uv run --no-sync python -m pokemon_hunter.beta.cli --root DISPOSABLE_COPY enable-pack-research
```

Staging's existing initialization path includes the additive table. No staging,
owner-root migration or deployment was executed. SQLite copied-state migration,
repeatability, empty-table schema rollback and preservation were rehearsed;
PostgreSQL execution remains unqualified in this slice.

For an independent fresh synthetic run (use unused output paths):

```sh
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output NEW_SEED
uv run --no-sync python scripts/rehearse_e5a.py --seed NEW_SEED --root NEW_COPY --output NEW_EVIDENCE
uv run --no-sync python scripts/serve_e3a.py --root NEW_COPY --output NEW_EVIDENCE
# Complete the ordinary browser walkthrough; stop/restart only this server.
uv run --no-sync python scripts/rehearse_e5a.py --root NEW_COPY --output NEW_EVIDENCE --verify
```

The server requires SYNTHETIC_ONLY, guards the supported loopback port and prohibits
/counts HTTP-client and eBay acquisition calls. After stopping it, allow its port
to leave the operating system's transient closing state before restarting. Preserve
its zero-call report before restart because this historical helper starts a new
counter per process. Never stop another listener or operate the owner installation.

## Remaining limits and next action

Retained public evidence covers partial catalog data and historical Target records.
Official contents, current purchasability, all-era coverage, separate-person review,
populated Production eBay, owner acceptance and full beta acceptance remain open.
No acquisition, refresh adapter, credentials, provider activation, purchase, bid,
hosting or owner deployment occurred.

Next bounded action: implement **E4a explicit bounded refresh orchestration with a
replay-only adapter**, retaining immutable observations, original times and per-source
failures. Keep live acquisition disabled until a supported source/access path is
separately authorized; qualify only offline engineering on fresh synthetic state.
