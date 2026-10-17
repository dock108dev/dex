# Private price snapshots

Versioned Shopping prices live under the existing private root's `price-snapshots/`,
with no network acquisition in the importer. Place an owner-only package in
`price-snapshots/staging/`. The contract and observation schemas are owned by
`beta/price_snapshot_contract.py`; lifecycle operations belong to `beta/price_snapshots.py`.
Ordinary roots require the exact independently reviewed contract digest in private
`price-contracts.json` (review ID to digest); a package cannot approve itself.
The engineering fixture provider is admitted only on a `SYNTHETIC_ONLY` root.

`dex-price-snapshot-v1` remains supported. A `dex-price-snapshot-v2` input has
`schema`, `version`, `release_month`, `contracts` and `records`. `contracts` maps
each review ID to its independent `contract` and `expires_at`; every observation
adds `contract_id`. Validation projects each source through the v1 rules. The
installed immutable `dex-price-release-v2` descriptor contains only release/source
identity; price records are separate owner-only source shards. Source seals are
removed with their prices, without rewriting another source's bytes.

**Only TCGCSV raw** fields may declare
`date_basis: publisher_build`, `valuation_date_field: null` and
`reference_date_field: last-updated.txt`. Those rows retain `as_of: null`, an
aware `publisher_built_at` and its UTC date in `reference_as_of`. The 30-day
age rule uses that date, with “provider valuation date unavailable” displayed.
Capture is separate. Graded and other sources still require valuation dates for
eligibility. This date policy installs no provider permission or actual records.

After source review and acquisition within the owner's current authorization,
preview and validate before activation. Set `DEX_APP_ROOT` using
[existing-installation startup](local-development.md#existing-installations); use
that root without initialization. These examples are operator writes, not checks
to run as part of ordinary testing:

```sh
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" price-preview --file "$DEX_APP_ROOT/price-snapshots/staging/release.json"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" price-validate --file "$DEX_APP_ROOT/price-snapshots/staging/release.json"
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" price-activate --file "$DEX_APP_ROOT/price-snapshots/staging/release.json" --expected-current none
```

Use the current release UUID instead of `none` for subsequent activations. Activation
consumes the staging file, records its integrity fingerprint and atomically swaps
one pointer. `price-rollback --expected-current UUID` refuses intervening changes;
`price-remove --version UUID` deletes managed content/fingerprints and excludes that
version from restore. `price-purge-expired` performs immediate managed-file cleanup.
Commands report counts/decisions, never prices. The ordinary server runs an expiry
worker; the calculator uses the same selection in browsing and evaluation, and
removes expired current-page prices while retaining quantities/wants.

`price-remove-source --contract-sha256 DIGEST` withdraws one exact contract across
managed releases and staging, deletes its price shards/seals and excludes restored
copies through a separate non-price source revocation registry. Unaffected sources
remain readable. Removing admission from `price-contracts.json` also removes that
source's v2 active/staged records on access or worker cleanup. Preserve both source
and release revocation registries outside restore. Browsing/evaluation choose the
newest admitted date, then capture timestamp, grader, contract digest and observation
ID; competing eligible observations remain separately identified, without averages.
Every saved reference and conflict needs its own surviving save rights. Current
pages check local source status each second; saved history performs no such refresh.

## Module boundaries and tests

`beta/lot_guides.py` projects legacy and private observations into cells, conflict
provenance and unavailable reasons. It takes admitted records explicitly; it does
not read the app root, ownership or catalog. `beta/lot_calculator.py` owns selectors,
session wants, preparation and permanent-save admission, and reexports its existing
cell functions for callers. Both browse and evaluation use the same projection.

Snapshot tests are grouped by contract:

- `tests/test_price_snapshots.py`: v1 lifecycle, validation, integrity and saving.
- `tests/test_price_snapshot_sources.py`: v2 source isolation, revocation and competition.
- `tests/test_price_snapshot_dates.py`: publisher-build versus valuation dates.
- `tests/price_snapshot_helpers.py`: shared synthetic setup and package builders,
  outside collected test modules. It reuses the existing synthetic Shopping fixtures.

Run these with the existing `dev`/`ci` environment described in
[development](local-development.md#testing):

```sh
uv run --no-sync pytest -q --disable-socket --allow-unix-socket tests/test_price_snapshots.py tests/test_price_snapshot_sources.py tests/test_price_snapshot_dates.py tests/test_lot_calculator.py tests/test_reference_policy_ssot.py
```

For backup exclusions, revocation preservation and deletion limits, use
[operations](operations.md#snapshot-retention-and-backups). Private snapshots,
contracts and source-review records are not shipped repository inputs. Coverage
depends on the selected installation's active release and source admission.
No scheduled acquisition is connected.

For a read-only investigation, `current` and `display_current` are unsuitable:
their expiry/source pruning can mutate managed files. Inspect the exact call graph
before selecting a helper; do not disable the ordinary worker to freeze state.
Use bounded metadata reads and pure contract validators with a read-only catalog
connection; keep private prices and contracts out of shared output. Local admission does
not establish provider freshness, seller identity or permanent-save rights. The
legacy hunt path does not consume these private observations; see
[Shopping discovery constraints](hunts.md#discovery-integration-constraints).

## Price Hunter reference requirements

HUNT-01's minimal batch adapter indexes admitted records by printing/legacy identity
before using the existing guide selection and literal reference applicability.
Every results read rechecks ordinary lifecycle; no values or derivatives are cached
durably. The separate `scripts/qualify_hunter.py --root EXISTING_ROOT --output FILE`
audit uses a read-only catalog connection and pure bounded admission checks without
calling pruning readers. It emits aggregate metadata only. The October 16 audit
found eligible references for 929 of 7,036 indexed identities and 6,107 unpriced;
seller condition/identity applicability is still required. HUNT-03 separates the
calculator's eleven-set browse selector from snapshot validation identities:
`price_snapshots.entries` now supplies all published Pokémon printings. Exact
independently reviewed contract/product/subtype mappings, field restrictions,
source admission, expiry and withdrawal still govern every record. This selector
extension grants neither source rights nor new records; the manual All cards
picker retains its existing scope.

Seller-specific condition, literal grader/grade and printing claims narrow the
already admitted local bucket before established date/source selection. A newer
inapplicable observation cannot hide an older applicable one. Competing applicable
sources remain separate with their own valuation, publisher-build, capture and
expiry dates and save restrictions. The ordinary calculator's source selection
and permanent-save admission remain unchanged.

The metadata-only audit found all 901 eligible snapshot identities inside those
eleven sets. Outside them, six identities had eligible retained guides and 5,716
were unpriced. All four indexed printings above species 251 and all 221
Trainer/Energy/other printings were unpriced. Thus the adapter extension has
engineering-fixture qualification, with no measured increase in actual snapshot
coverage. No new feed, refresh, import or provider operation occurred.

The selected [Price Hunter](hunts.md#selected-price-hunter-requirements) needs a
current, applicable reference for each priced identity it attempts to compare.
The importer and lifecycle above exist; a connected all-Pokémon reference refresh
does not. Its first slice batch-matches broad live listing summaries to existing
local admitted references. It needs no price API call per offer or complete new
catalog/feed before querying listings. Broader reference acquisition is a separate
improvement where measured gaps require it. The earlier vintage coverage audit
is dated evidence, not today's priced universe. A new metadata-only audit must
count eligible, stale, unpriced and
unmapped identities without copying private prices or contracts into reports.

Reuse admission, canonical product/subtype identity, source competition, exact
grader/grade applicability, atomic activation, expiry and independent withdrawal.
Do not add a second guide store or treat eBay asking prices as realized market value.
Fresh-source acquisition requires a supported source contract and finite pacing,
request/body/time limits and consumed attempts; daily source publication is not
permission for per-listing refresh. Existing package size/row limits require
bounded sharding or a qualified extension for larger coverage, not an unbounded import.

Keep provider valuation time, publisher build, capture, activation, last attempted
refresh and expiry distinct. In particular, the admitted TCGCSV raw exception
retains null provider valuation time even after a newer publisher build is imported.
[TCGCSV documentation](https://tcgcsv.com/docs) and [FAQ](https://tcgcsv.com/faq)
describe cached market data and publication/pacing limits; they do not establish
per-card current condition, live transaction prices or application-specific rights.
A recently fetched listing can be compared against a labeled dated reference
without converting that reference into a fresh quote.

Any source freshness policy must state which time it uses, the permitted maximum
age and what happens when the date is unknown. Missing, stale, conflicting,
withdrawn or nonapplicable references stay unpriced/conditional as appropriate.
The hunter must not label an unsupported comparison confirmed under market or EV.
Retain display/arithmetic/storage/save/export rights independently; broad hunting
does not relax source deletion, backup or temporary-result rules.

For the selected [lot-content step](hunts.md#added-step-lot-contents), apply the same
reference eligibility to each reviewed card/quantity. A seller's whole-lot amount
is separate from the sum of its priced contents. Unmatched, ambiguous or unpriced
contents remain a coverage gap, never a zero-valued contribution that makes a
partial subtotal look like a full lot valuation.

HUNT-05 rebuilds separate BIN/current-bid/minimum-next/manual scenarios on every
local admitted-reference read. Ranks are scoped to equivalent cost components;
known shipping participates, unknown costs remain null, and no auction gap is a
bid limit. LOT-01 quantity-multiplies applicable references through the existing
Ungraded engine with one whole-lot amount. Unresolved/unpriced remainder cannot
become a complete lot value. No source, feed, reference store or actual coverage
expansion is added. See [backend contracts](hunts.md#hunt-0405-and-lot-01-backend-contracts).
