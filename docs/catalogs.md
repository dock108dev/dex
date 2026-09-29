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

Vintage completion counts distinct eligible species. Set and custom goals retain
their own scope; acquiring duplicates does not inflate unique completion. Guide
scenarios are conditional, dated estimates with visible source and coverage;
unknown and stale values remain unavailable.
