# Catalogs and collection workflows

Catalog entries describe printings; physical copies describe what a user owns.
Shared catalog publication never silently rewrites ownership. Copies may retain
provisional identity and unresolved edition, finish or language information.

The synthetic seed publishes packaged metadata for the vintage sets and Gym Heroes,
plus explicitly synthetic test entries. The original app uses its own pinned
catalogs under `config/catalog/`. Metadata availability does not grant image,
pricing or trademark redistribution rights.

Users can request missing catalog coverage from a scan or provisional copy.
Private photos are available to reviewers only with explicit consent. Owner-role
review uses versioned packages, preview, verification, publication and rollback.
Resolved catalog identities update the same copy through the supported service
path; they do not create an extra owned copy. Package schemas and validation live
in `beta/catalog_imports.py`; request access rules live in `beta/catalog_requests.py`.
`scripts/prepare_tcgdex_package.py` converts a saved provider response into that
format; it does not itself qualify source rights or publish a catalog.

Collection additions, edits, removals, set batches and imports use preview and
confirmation. Operation IDs prevent duplicate confirmation; undo refuses to
clobber later edits. Imports report invalid rows before confirmation. Exports
retain copy identity, goals, binders and unresolved attributes.

The goal builder filters published entries by available game, selected sets,
card type and rarity. Pokémon goals can also select a Pokédex range within
#001–251. Species completion counts one eligible printing per species from those
filters; printing completion counts the selected catalog entries. Original 151,
Vintage 251 and Johto are presets in the same builder. Set and custom checklists
remain available.

Saving a goal freezes its membership and catalog version; create a new version
to change its scope. Species without matching printings stay in the denominator
and are shown as unavailable. A duplicate does not inflate unique completion,
and a copy outside the selected sets does not satisfy that goal. Exact-variant
policy requires resolved identity. Goal-scoped [eBay hunts](hunts.md) search the
missing members using current account-owned copies. Bargain searches can include
owned cards and use goals as optional catalog filters; searches never add inventory.

Guide scenarios are conditional, dated estimates with visible source and coverage;
unknown and stale values remain unavailable.
