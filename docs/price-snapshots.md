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
