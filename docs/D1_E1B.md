# D1/E1b — reviewed English 151 and publication bridge

The bounded engineering slice is delivered. Full D1/E1 and beta acceptance remain
partial. This working-tree candidate preserves the previous D1/E1 candidate and
owner edits on HEAD `fba1be13135b0b3bbb6cb674de5586e0f3c80740`. The prior manifest
SHA-256 `c6cb7a3aa6123db3c71499fe2cb86cb54027968525b6d798267efbab62348f53`
and all 23 listed files matched before implementation. No owner installation was
read or modified. No commit, remote publication, purchase or ownership change ran.

## Real data and unresolved gates

[Versioned package](../config/sealed/2026-10-04-151/package.json) and
[reconciliation](../config/sealed/2026-10-04-151/reconciliation.json) reconcile all
207 numbered identities in the retained [official 151 checklist](https://assets.pokemon.com/assets/cms2-en-uk/pdf/trading-card-game/checklist/mew_web_cardlist_en.pdf)
against TCGdex English set/card details. Numbers include 151 base Pokémon,
additional Pokémon illustrations, Trainers and numbered Psychic Energy #207;
207 is neither a species count nor a physical-variant count. All Pokémon records
resolve canonical National Dex IDs; Trainers/Energy have no species mappings.
The registry still holds 1,025 species and the provider universe 220 sets
(205 physical, 15 digital). This does not reconcile the complete official universe.

384 provider-described variants are normalized with distinct language/finish/variant
identities. Every numbered standard-set variant has official checklist membership:
207 booster rows. 177 reverse, stamped, alternate-foil, oversized/metal or other
provider-described variants retain individually documented membership gaps. A
provider variant listing is not proof of US distribution, separate physical issue,
or booster availability. The checklist visually distinguishes standard nonfoil and
standard foil; it does not establish these extra variants' membership. Unresolved
variants remain catalog records with unknown membership. No promo/deck classification
was invented. The old Scyther normal printing and pool record remain byte-identical.

One provider, one expansion: 206 new detail requests, no retries, plus one reused
Scyther detail response. No detail attempt failed. Every request outcome, original
time and raw hash is retained in the private acquisition index. Raw details contain
excluded third-party pricing/artwork/rules; public packages retain metadata and hashes.
The original MIT license remains in `config/sealed/2026-10-04/TCGDEX_LICENSE.txt`.

The exact product remains UPC 820650853210 / Target TCIN 88897904, version
`2023-US-English-single-bundle`. The [official gallery](https://www.pokemon.com/us/pokemon-tcg/product-gallery/scarlet-violet-151-booster-bundle)
returned a tool access error; the [official 151 page](https://tcg.pokemon.com/en-us/expansions/151/)
returned only an unusable iframe. Two distinct official page attempts were consumed;
no retry/bypass followed. Neither corroborates exact product contents. Target's
six-pack description stays a retailer claim. Total packs and expansion quantity
remain null; guaranteed inclusions remain unknown, not zero.

One retailer page was read: [Target](https://www.target.com/p/-/A-88897904), matching
TCIN/UPC/DPCI. Its product section reports USD 27.99 and out of stock. Actual seller,
direct-versus-marketplace status and shipping price remain unknown. Add-to-cart
text alongside out-of-stock does not establish purchasability. The old unknown
observation remains; the new extracted observation is separate. The original read
time is approximate, bounded by the immediately subsequent checklist extraction
file time, and explicitly labeled; exact backend observation time is unavailable.
No import, reopening or report refreshes it. This is a retained tool extraction,
not a full raw HTML capture or an independently witnessed offer. The extracted
JSON's hash and quality limitations are in source metadata. No current purchasable
offer is established. Previous Pokémon Center denial evidence remains preserved;
it was not retried or attached to an unverified equivalent product.

The [missing-18 report](../config/sealed/2026-10-04-151/missing-18.json) now identifies
normalized printings and standard booster relationships for every row. Its state
is `printing-and-standard-booster-researched`; official contents, purchase availability,
independent Scyther review and owner acceptance remain open. Account ownership was
not inferred from the research seed. Old/new catalog counts are never summed as
all-era integrated coverage.

## Reviewed bridge and correction/version rules

`sealed_bridge.py` reuses `catalog_imports` preview/verify/publish/rollback with
owner authorization, existing audit journals and the shared transaction/advisory
lock. Preview returns all 384 sealed-to-collection IDs, explicit provider expansion
mapping, additions/updates, conflicts and downstream impact. The existing catalog's
canonical set key is `sv03-5`; the actual provider `sv03.5` ID is retained as an
additional reserved mapping and reviewed alias. Exact provider printing IDs include
variant suffixes. Existing IDs/mappings cannot be redirected; duplicate identities
or implicit archival of other collection printings fail. A failed step rolls back
both catalogs and their journals. Collection publishing never creates copies or
automatically enrolls printings into frozen goals.

Optional `corrections` bind kind/ID to the prior record fingerprint and a review
reason. Printing names/rarity, species/expansion names, product descriptive contents,
pack quantities and coverage gaps have explicit allowed fields; every correction
retains old sources and adds source provenance. Product-content authority checks
still apply. IDs, category, species mapping, language, number, finish, variant,
product version/SKU and external mappings cannot be repurposed. Source observations
remain immutable: new checks need new source/observation IDs. A genuinely new
identity/version uses a new record and distinct external mapping; conflicting
reuse is rejected for explicit future reconciliation, not silently resolved.

Correction preview shows before/after meaning. Structural verify does not assert
source truth or owner acceptance. Intervening catalog changes invalidate reviews.
Published corrections are idempotent on repeated import. A printing already bridged
requires a compatible reviewed bridge in its correction package, preventing drift
between catalogs. Prior data/provenance remain in immutable journal baselines and
packages. Rollback restores prior descriptive meaning, retains later unrelated
observations and refuses conflicting edits/dependencies; bridged rollback also
requires an unchanged collection publication. Reserved identities survive archival.
Full browser correction UX and broader identity-conflict resolution remain future work.

## Offline reproduction and disposable rehearsal

Private retained sources:
`/Users/michaelfuscoletti/dex-private/d1-e1b-20261004/source-evidence`.
`index.json`, `attempts.json` and `retained-hashes.json` pin every reused/detail input
and extracted web observation. Hash mismatches fail before normalization. No network
calls occur in either script. Normalization requires the local `pdftotext` executable;
the official PDF's numbered rows are parsed and its visual foil legend was operator
reviewed. Normalization reproduced every public artifact byte-for-byte.

```sh
uv run --no-sync python scripts/prepare_151_expansion.py \
  --sources /Users/michaelfuscoletti/dex-private/d1-e1b-20261004/source-evidence \
  --baseline config/sealed/2026-10-04/package.json --output NEW_OUTPUT_DIR
uv run --no-sync python -m pokemon_hunter.beta.sealed_cli validate config/sealed/2026-10-04-151/package.json
uv run --no-sync python -m pokemon_hunter.beta.synthetic --output NEW_SYNTHETIC_ROOT
uv run --no-sync python scripts/rehearse_151_expansion.py --root NEW_SYNTHETIC_ROOT \
  --package config/sealed/2026-10-04-151/package.json --output NEW_EVIDENCE_DIR
```

Manual operator flow uses `sealed_cli --root NEW_SYNTHETIC_ROOT migrate`, then
`preview PACKAGE`, `verify IMPORT_ID`, `publish IMPORT_ID`, `report --json`, and
`rollback IMPORT_ID`. Read the actual review/mapping projection before verify.
Correction packages use the same commands. Rehearsal evidence includes an explicitly
synthetic correction package, its review and rollback. To replay that correction,
publish the base package on a new root first, then preview the retained
`synthetic-correction.json`. It demonstrates behavior, not real metadata truth.
Each re-publication after rollback uses a fresh sealed and bridge package version.
The old generic foundation rehearsal expects no collection metadata changes; use
the new 151 rehearsal for bridged packages.

The copied-state rehearsal compares all pre-existing account/copy/goal/photo/hunt/
reservation rows exactly, and preserves each old catalog row/mapping while allowing
new reviewed metadata and audit journals. It exercises migration twice, publication,
repeat imports, synthetic correction, correction rollback, publication rollback,
SQLite backup/recovery and recovery publication. Final root/evidence paths and
checks are recorded in [dated validation](history/2026-10-04-D1-E1B-VALIDATION.md).
PostgreSQL runtime, hosted checks, device evidence, independent source review and
owner acceptance were not performed.

## Next bounded slice

E2a: create an explicit versioned Original 151 goal across currently reviewed
published printings, preserving every existing frozen goal and its policy. Show
account-derived missing-species results and separate unavailable catalog coverage.
Add explicit goal-version preview/update and copied-state/vintage/account-isolation
checks. Use this candidate and reviewed data; acquire no broader catalog or retailer
data, implement no pack-shopping UI and leave official contents, 177 membership
gaps, independent Scyther review, eBay Production and owner acceptance open.
