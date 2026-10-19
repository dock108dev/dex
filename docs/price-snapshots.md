# Private price snapshots

Private snapshots are explicit, independently admitted reference inputs. Importing
a package makes no network request. Reading, capture or activation does not create
a fresh valuation date or grant storage rights.

## Contracts and lifecycle

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
"$DEX_APP_PYTHON" -I -m pokemon_hunter.beta.cli --root "$DEX_APP_ROOT" price-activate --file "$DEX_APP_ROOT/price-snapshots/staging/release.json" --expected-current "$CURRENT_RELEASE"
```

Set `CURRENT_RELEASE` to the actual active release UUID, or `none` only when no
release is active. Activation
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

## Offline preparation

`tcgcsv_offline.py` and `tcgcsv_prepare.py` validate supplied retained feeds and
literal catalog bindings. Their command-line adapter is
`scripts/prepare_tcgcsv_offline.py`; inspect `--help` for required manifest, report,
contract and expected-current inputs. Default preparation reports metadata only;
staging is an explicit separate write and never activates a release.

Products, subtypes, numbering, language, condition, currency and source identity
must agree with reviewed bindings. Unsupported graded/special variants, incomplete
scope, malformed feeds and missing or conflicting builds are refused. TCGCSV
publisher-build references retain a null provider valuation date. Limits are owned
by `tcgcsv_offline.py` and `price_snapshot_contract.py`; source shards and composed
releases have separate bounds. No scheduled acquisition is connected.

Capture tooling is separate from preparation and activation. A reviewed plan and
durable noncontent accounting constrain selected resources, pacing, byte limits,
Stop and uncertainty. Restart, rename, failed attempts and app restore never renew
consumed capacity. Hard-coded finite qualification allocations are not reusable
provider budgets. See [operations](operations.md#snapshot-retention-and-backups).

## Beta population accepted — coverage work stopped

Imported from the Desktop tracker during the October 18 documentation cleanup.
This is a historical closeout/decision, not a fresh verification. The active
Shopping repair in [Shopping](hunts.md#active-owner-direction--shopping-repair-first-october-18-2026)
and the Desktop Next Steps plan govern current work. Historical next actions below
do not reactivate deferred work or establish installed delivery.

**Owner decision:** the current catalog and reference population is good enough
for the beta. Stop pursuing the remaining percentage. Further real data pipeline,
coverage expansion and residual identity/pricing campaigns are deferred until the
owner chooses to resume them. REFERENCE-R3/RESIDUAL-1 is **parked**, not the next
assignment. No further preparation, native catalog publication or acquisition is
needed merely to improve the current coverage number.

Historical pre-recovery delivery measurements follow. The old root below was
subsequently deleted; managed prices were not recovered. These measurements do not
establish current availability; see [recovery](local-development.md#existing-installations).

At that delivery:

- **33,083 identities / 187 sets; 19,365 eligible / 13,718 unpriced** — **58.5%**,
  roughly 60%, accepted by the owner as the current beta population.
- **23,355 observations / 22 independently managed sources**. Active release
  `2af89c05-d3a2-49d7-b325-ad3304c59304`.
- **207 active copies / three frozen goals**, protected customer state and all
  59 database tables/schemas preserved.
- Root `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`,
  normal URL `http://127.0.0.1:8011/`. Last verified runtime:
  `/Users/michaelfuscoletti/.local/share/dex/runtimes/catalog-additive-release-20261017/bin/python`;
  wheel SHA-256 `115a336d4e36df4a64e268f587311810f71bc8f4a7396471d601c21290b2609f`.
- R3/ACQUIRE-1 delivered 6,117 new observations/eligible children, with **98/98
  requests consumed**. REFRESH-1 and S6 are also exhausted. No standing allowance,
  retry, pipeline, schedule or polling follows from those completed selections.

These are delivery measurements, not a new runtime audit performed by this tracker
edit. Existing dated-reference/conditional/unpriced labels and normal source expiry
and withdrawal behavior remain intact. Population acceptance does not change them.

Actual delivered closeout: `reports/reference-r3-acquire1-20261018/closeout.md`,
coverage: `reports/reference-r3-acquire1-20261018/coverage-final.json`,
preservation: `reports/reference-r3-acquire1-20261018/preservation-summary.json`.
