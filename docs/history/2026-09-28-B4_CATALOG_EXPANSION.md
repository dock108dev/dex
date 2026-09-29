# B4 catalog expansion — local pre-alpha

September 28, 2026. Implements the private request → admin review → versioned publication → existing-copy resolution loop in the authenticated app. B3 remains simulated; actual owner provisioning, real recognition evaluation and hosted qualification are independent open items. No deployment, purchases, marketplace search or live collection cutover occurred.

## Walkthrough

1. Open Scan/Add, upload a card and save it as unidentified, or start from an existing provisional copy in Collection. Choose **Request catalog support**.
2. Supply optional game, set/language and card name/collector-number hints. Hints are submitted to reviewers. Photos stay private unless **Share retained photos with catalog reviewers** is checked. Consent can be revoked from the request at any time. Repeated submission from the same scan/copy returns its existing request.
3. The owner-role account opens **Catalog review**. Triage requests, assign a reviewed game/set/language identity, record aliases, request evidence, reject, or merge into another request. Reviewers see submitted hints and only specifically shared, still-available photos. They cannot open another collector's raw inventory or scan-photo URLs.
4. Load the included Gym Heroes package, or choose another valid metadata package. Preview the full additions/changes/archives, count/coverage, source hash/version and separate metadata/image permissions. Verify the preview, then publish. A later edit to the catalog invalidates stale previews. Publication is atomic; an exception rolls back every write.
5. Owners reopen their requests to see proposed matches. Name, collector number and supplied variant clues must agree within the reviewed set/language. A set alone does not identify a card. Correct hints when necessary. **Accept for this existing copy** is explicit confirmation and updates that copy through the ordinary inventory journal. It retains ID, notes, attributes, original scan provenance and photos. Retries return the same resolution. Undo is available in Settings and respects later edits.
6. Roll back a publication from Catalog review. Retained IDs and external mappings remain; newly unpublished entries are archived, not deleted. Referenced copies survive and display in Collection/export. Republishing restores active coverage. Archived entries cannot be newly chosen as catalog matches; import of an existing exported archived identity remains possible. Frozen goal membership never changes on publication or rollback.

## Catalog source and permissions

Added set: **English Gym Heroes**, 132 catalog entries, outside the initial ten sets.

- Source: [TCGdex set metadata](https://api.tcgdex.net/v2/en/sets/gym1), retrieved September 28, 2026.
- Raw response SHA-256: `9d19156dc3b163b94957f52fe1a9d18ab2c42aa1c12945ff8d0a9fbf0d56a7aa`; version `2026-09-28-9d19156dc3b1`.
- Metadata permission: TCGdex states its database is [MIT licensed](https://github.com/tcgdex/cards-database#licenses); the [license](https://github.com/tcgdex/cards-database/blob/master/LICENSE) is retained in `config/catalog-imports/TCGDEX_LICENSE.txt`.
- Only card names, string collector numbers, external identifiers and set metadata are included. Artwork, image URLs, card rules text and prices are omitted. The database license is not treated as permission to redistribute Pokémon artwork or trademarks. Hosted/source review remains a later gate.
- Coverage is the source's 132 numbered entries. Edition, finish and variant are unknown, not fabricated from aggregate counts or rarity. This is not a complete variant/master-set claim. The source's compact set response omits rarity/type/species metadata; new entries show unknown for those fields. Gym Heroes does not expand the frozen Vintage 251 checklist.

The saved raw source is private evidence, not an application runtime dependency. `scripts/prepare_tcgdex_package.py` reproducibly converts a saved English set response into the ordinary `dex-catalog-v1` package. It makes no network calls and does not import ownership. The included package uses that converter and the same preview/verify/publish/rollback routes as any other package; no direct set seeding occurs.

## Shared design and safeguards

Game adapter declarations live in `catalog_imports.ADAPTERS`. Pokémon and **Synthetic Orbits (test game)** use the same catalog tables, external mappings, requests, matcher, inventory mutations, exports and goals. The synthetic package deliberately uses `AX-007/A` numbers and two `orbit:plain` / `orbit:nebula` variants at the same number, with no Pokémon species. It is an original test fixture, not real coverage for another TCG. The synthetic package is available for operator review, but is not automatically published into the regular review app.

Canonical request identity is game + language + reviewed set key. Only reviewed aliases participate in automatic deduplication; arbitrary name guesses remain separate until triage. Merge preserves all private submissions, photo-consent decisions and their provenance. Demand is `COUNT(DISTINCT user_id)`, not upload count. Merge cycles and stale review revisions are rejected. Rejection and merge never delete a card. A merged submitter follows the destination's current status. Thirty new request origins per user per rolling day bound local intake.

Imported sets have stable game/set/language IDs; printings have stable provider/language/external IDs. Collector numbers remain strings, including leading zeros, slashes and prefixes. Duplicate external identities, duplicate number/variant combinations, reused source versions with changed content, repurposed external IDs and conflicting source mappings fail validation. A different source cannot silently duplicate an existing identity. Manual source-identity reconciliation remains an operator/code task rather than an automatic guess.

Each import retains its normalized package, content hash, immutable preview, before snapshot, current publication signature and actor audit. States are preview, verified, published and rolled-back. Request states cover new, needs-evidence, ready, ingesting, verified, published, rejected and merged. Operator verification is an explicit review of the source/coverage preview; shape validation alone is not proof of third-party catalog truth. Import packages are capped at 2,000 rows, and partial coverage must be declared. Synchronous atomic publication is appropriate for these bounded local packages; no new job platform is introduced.

Rollback retains referenced identities and the mapping history, and restores the prior active catalog view. It does not undo ownership or silently reassign an existing copy. Exact-variant goal completion excludes archived printings; membership and denominator remain frozen. Resolution removes only identity uncertainties established by the selected catalog row; unresolved edition/finish/variant stay explicit. New metadata has no pricing fallback and does not inherit legacy guide values.

Photo permission is scoped to a particular submission and its source scan. Every evidence read rechecks reviewer role, current sharing consent, active submitter account, photo ownership, retention and copy availability. Deleting photos or revoking consent immediately removes reviewer access. No private notes, whole collection or blanket photo permission accompany catalog administration. B3 retention, API reservations and disable settings are unchanged. Audit/job histories contain metadata, not copied image bytes. Private backups remain separately retained and require operator deletion; full hosted erasure/backup expiry is B5 work.

## Local setup and review environment

The existing review environment and login are preserved. Back up its database before schema upgrades; then enable B4 using:

```sh
uv run python -m pokemon_hunter.beta.cli --root PRIVATE_ROOT enable-catalog
```

The root must already have B3 enabled. This idempotent local migration adds catalog/request tables and publication-state columns, preserving account mappings and inventory. Restart the server to expose Catalog requests and Catalog review. On an existing isolated root, never rerun initialization or reset the password.

Review URLs: `http://127.0.0.1:8011/requests/` and owner-only `http://127.0.0.1:8011/catalog-review/`. Review root remains `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`.

The English Gym Heroes package is published in that copied review catalog after passing the ordinary importer lifecycle in independent verification environments. Existing private inventory is not changed to demonstrate the loop. The owner can upload/save an unidentified card and request its known set to review the resolution flow. To rehearse publication from an empty catalog, use a fresh B4 root and the included package, not a reset of the review environment.

## Recognition and remaining limits

No `OPENAI_API_KEY` was available in the implementation environment. **Zero real recognition calls and $0 API spend** in B4; correct/wrong/unresolved rates, real latency and actual returned usage costs are unmeasured. Suitable consented evaluation photos plus a securely configured key remain prerequisites for the bounded B3 evaluation. Existing reservations were preserved, not reset. Fixture outcomes, synthetic game checks and browser images are engineering evidence only.

B3 runtime `a456ab7` and documentation closeout `1e99996` remain historical exact candidates. B4 source identity, clean-checkout/browser results, source/review preservation, source metadata and publication evidence are retained privately under `/Users/michaelfuscoletti/dex-private/b4-catalog-20260928/`; final identity is in `handoff.json`. Failed browser attempts are retained separately and never presented as successful evidence. They exposed one consent-form lookup bug for digit-leading request IDs (fixed); other harness corrections respected CSP and the existing 48-entry pagination. No real-device, hosted, actual-owner or pilot acceptance is claimed.

## Verified B4 candidate

Tested runtime commit: `9dc074d8d05ed94f88a6c278502b30d5ae9dc424`; source tree: `007f7808ce2b02f9f5d996ec71becea03addc014`. Later documentation-only closeout does not change this runtime test identity.

- 188 tests passed in both working and clean checkouts; lint and formatting passed. One existing Starlette TestClient deprecation warning remains.
- Complete restored B2 parity, B3 confirmation/undo and B4 request/consent/triage/publication/same-copy resolution/rollback/republish browser flows passed in desktop and narrow Chromium. B4 screenshots were inspected. These are not real-device results.
- Tests cover cross-account isolation, merge/demand counts, repeated imports, identity conflicts, partial coverage, interrupted atomic publication, rollback with referenced copies, concurrent retry-safe resolution, frozen goals and the synthetic second-game adapter.
- Original source data and restored legacy smoke checks passed. Every pre-existing review database row, credential/configuration file and recognition reservation was preserved. Gym Heroes passed preview, verification, publication, rollback and republication in the preserved review environment.
- Private reports: `clean-regression.txt`, `clean-browser/browser-report.json`, `clean-browser/b4-browser-report.json`, `preservation.json`, `review-preservation.json` and `review-publication.json` under the B4 evidence directory above.
