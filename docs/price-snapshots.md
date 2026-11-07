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

## Shopping comparison at scale

Explicit multi-source activation validates the full release, writes each independently sealed source and prepares a private `.idx` file beside that source. It contains byte ranges into the sole managed price copy, rights metadata and the source fingerprint. Removing a source removes its index. Indexes belong under the same backup and retention exclusions as their shards.

A reviewed lot looks up the included printing IDs. Each decision checks the active version, source approvals, independent revocations, expiry, shard and index integrity, current printing identity, and the reviewed condition or literal grade. A new process verifies file digests before using an index. While file identity, size and modification/change times remain identical it can reuse that verification. It does not cache prices or a computed ceiling. A missing or stale index withholds the recommendation. An explicit purge continues to own physical reclamation.

For an existing split release, the operator can prepare the surviving authorized sources again using `price-activate` with its installed version descriptor as `--file` and the same active version as `--expected-current`. Use the ordinary installation procedure only under separately approved delivery or maintenance scope. Independent source withdrawals remain in force. See [qualification boundaries](CI.md#integrated-shopping-decision-qualification).

## Read-only lot-value readiness

The source operator `scripts/lot_value_readiness.py --root "$DEX_APP_ROOT"` exposes
bounded metadata coverage without application setup, acquisition, pruning or
activation. Run it with the checkout's provisioned engineering interpreter. It
separates dated raw guides from condition-applicable lot values, source lifecycle
from approvals, and catalog inventory from checkout/runtime compatibility. A completed
inspection may still report blocked readiness; its exit code alone is not a price gate.
This operator is not installed application behavior or a replacement price store.

## Evidence and offline refresh

`dex-price-contract-v2` extends the existing v1/v2 snapshot containers; it does not
create a second price store. Its `valuation` policy separates `guide` from
`sold_estimate`, nullable raw condition, item-only USD basis, optional
`ceiling_applicable`, qualification/review, estimator parameters and admitted original
sale origins. Each v2 row carries the checked `dex-valuation-evidence-v2` envelope.
V1 contracts remain readable. Derived sold rows have `original_money: null`; original
transaction amounts remain in their sale evidence, never relabelled as a provider
quote. No real v2 source contract is admitted by this change.

`sold_estimates.py` is a bounded experiment: at most 2,000 supplied sale records and
16 MiB per estimate, exact printing/raw matching, unique original-marketplace sale
IDs, explicit amount/offer semantics and single-unit item-only USD. It excludes
unknown accepted offers, asking prices, incompatible currencies/shipping bases,
conflicting duplicates, unsupported quantities, future dates and out-of-window sales.
It preserves condition strata, unique/effective counts, exclusions and descriptive
spread. Unknown condition stays unknown. No per-card shipping is added to card value.

`valuation_evidence.py` reproduces a supplied estimate at validation, preserves sale,
capture and calculation dates, and requires source expiry within one day of calculation
and the oldest contributing sale's lookback boundary. The 30-day guide-date rule is
unchanged; 90-day sale lookback is a distinct age-labelled candidate, not fresh-price
proof. Independent review must qualify coefficients and source rights. Engineering-only
contracts are rejected on ordinary roots. Sold medians never supply strict ceilings.
The new selector chooses one qualified sold estimate, otherwise an eligible guide;
it does not pool guides with their underlying sales. Old guide consumers omit sold
estimates rather than relabelling them. Lot arithmetic and ranking consume these admitted evidence records through the
shared calculator and automatic Hunt projection.

`reference_preparation.prepare` validates and stages an already acquired package,
using existing catalog, source admission, managed storage and revocation services.
It has no transport, provider allowance, scheduler or recurring activation. Explicit
`activate` uses the existing atomic expected-current check and source indexes, with
Stop rechecked inside the activation lock. Failed preparation leaves the active
release untouched; ordinary expiry/withdrawal still withholds invalid old values.

Preparation has a nonblocking execution lock, a cooperative 30-second deadline,
existing package/row/byte ceilings and 1,000 finite noncontent reservations. Reservations
live under the existing independent `.dex-price-revocations/` parent in a per-root
`*-preparation` directory. A semantic package fingerprint excludes renamed release
and observation IDs and recapture timestamps. Interrupted/failed work remains consumed;
there is no reset/refund or automatic replay. `stop` persists until explicit `resume`,
which does not restore capacity. Keep this accounting outside restore and price removal.
Provider accounting stays separate: these offline reservations spend zero provider
operations and cannot replenish historical capture allowances.

The read-only `scripts/lot_value_readiness.py` now defaults to `--version 2`; explicit
`--version 1` and the v1 Python default preserve older consumers. V2 separates eligible
broad sold/guide coverage, condition-scoped references, condition-specific ceiling
applicability, exact catalog metadata, variant/set denominators and runtime compatibility.
Its top-level `ready` requires complete broad catalog benchmark coverage with actual
evidence; `partial` can still contain useful per-printing references. It is not a
whole-lot, account, delivery or provider-entitlement claim. Synthetic evidence is
labelled and never reports actual readiness. No acquisition or cleanup occurs on read.

Source compatibility is distinct from installed capability and active references.
Inspect the current installation before reporting guide or sold coverage.

## Publisher-native guides

`dex-price-contract-v3` and `dex-valuation-evidence-v3` add the explicit
`publisher_native_guide` branch inside the existing snapshot containers and source
store. The branch preserves unknown shipping and tax, raw mixed condition, exact
USD per-card publisher amounts, original source/build dates and independent rights.
It does not relax v2's item-only rule. Exact independent contract admission is still
required; a historical normalized draft for that field remains inadmissible.
Retain its original identity; do not reinterpret it as an approved contract.

Native observations require known applicable physical attributes and exact provider
mapping; conditional population semantics cannot fill unknown edition, finish or
language. Complete ordinary identities need no invented extra variant label. Missing
catalog/source representation remains unavailable. No source metadata or price is
acquired by validation, selection, calculation or display.

An explicitly selected `metadata_new_build` capture may check for a newer publisher
build without the operator's default rolling 24-hour wait. It requires a unique
recorded timing selection and existing history. An unchanged or older build stops
after the marker, before group metadata; consumed selections cannot replay. Product
refresh remains separately reviewed and newer-build gated. Stop, request spacing,
input bounds, private retention and source admission are unchanged.

`valuation_evidence.select` takes an explicit normalized/native purpose; normalized
selection retains qualified sold-first/guide fallback and excludes native evidence.
`lot_guides.native_cell` is separate from existing normalized guide cells. The shared
`shopping_math.native_subtotals` uses the existing Decimal, quantity and money caps,
with no mixed-cohort or native/normalized totals. Cohorts pin provider, field policy,
semantic policy version, currency/unit, condition/money basis and reference/build date.
Native arithmetic uses UTC reference dates consistently at local-day boundaries.

The listing assessment and discovery result projection carry native totals/subtotals
in a distinct field. They require scoped seller identity evidence and reconciled
quantities for a complete native total. Native results never fill normalized totals,
delivered differences, savings, sold inputs or strict ceilings. The minimal Publisher
guide sort groups compatible source/date cohorts and complete/partial results; it
orders complete same-cohort guide contents, not bargains. Offer costs remain separate.

New native prepared indexes use format 2 with admitted non-price source context;
older format-1-only runtimes reject them. Existing v1/v2 normalized indexes and
contracts retain their formats/semantics. No index can approve its source. The
ordinary source shards, seals, expiry, independent revocations, Stop/CAS preparation
and lifecycle reads remain authoritative. Native page references participate in the
existing local source checks, and invalidation removes dependent amounts while
preserving catalog alternatives and unrelated valid normalized references.

Native references and subtotals are ephemeral in this implementation. Existing
normalized saved-comparison admission explicitly rejects their underlying native
observation, even if a caller strips the displayed basis. Source permission for
immutable saving is not sufficient to bypass the missing native-history contract.
No native amounts enter metadata reports, catalog relations or new accounting stores.

Readiness version 3 reports native exact-printing coverage and parents with eligible
exact child alternatives separately from normalized/sold readiness and the original
catalog denominator. It cannot infer provider-wide source absence from inactive
references. Fixture references remain isolated engineering evidence, never actual
customer coverage.

## Native offline input preparation

The TCGCSV offline adapter now emits `dex-valuation-evidence-v3` when supplied an
independently reviewed v3 native contract. It preserves the literal publisher amount,
unknown shipping/tax, null condition, publisher build and original capture dates.
Exact physical applicability still gates each row; absent edition is not inferred.
This adapter rejects a v2 normalized `marketPrice` contract because that field's
shipping/tax normalization is not established. Existing v1 compatibility is retained.
Preparation is local and nonactivating; source admission, finite acquisition, staging
and CAS activation retain separate authorities. Each operation needs an exact
reviewed input/retention scope and admission digest. Adapter support alone creates
no active source or current coverage.
