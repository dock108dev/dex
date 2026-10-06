# D1c — retained English catalog coverage reconciliation

Dated October 5, 2026 (America/New_York). **D1c complete relative to the retained
October 4 universe; D1 all-era import coverage remains partial.** No acquisition,
import, publication, provider activation or owner-installation access occurred.
This is an offline reconciliation of retained real-source metadata and historical
synthetic publication evidence, not a current worldwide catalog verification.

## Baseline and source authority

HEAD `16766b5c160c0bac370c1177387662646bf51b42` matched. E6a candidate
`evidence/e6a-20261005/validation-final/candidate.json` SHA-256
`0a9f5f263fb7799b9997ffd6f6dff0ebd907932cfc187bb6791b6f8f6c405883`
matched, with **all 755 listed files matching before work**. Inherited edits and
all earlier evidence/manifests are preserved. No applicable AGENTS.md was present
in the repository or ancestor directories. Read the Desktop tracker, beta contract,
catalog guide, D1/E1, D1/E1b and E6a records before reconciliation.

The machine-readable [input lock](../evidence/d1c-20261005/inputs.json) hashes
all assessed packages, manifests, journals/projections and cited raw universe
inputs. [Source verification](../evidence/d1c-20261005/source-verification.json)
records URLs, exact original UTC retrieval times, hashes and retained paths.
References to URLs are provenance only; none was opened during D1c.

- `config/sealed/2026-10-04/universe.json` is the normalized dated English
  TCGdex REST v2 universe. `/v2/en/sets` was retained October 4 at
  `22:57:28.285573+00:00`; series responses followed at `22:58:50` UTC.
  Raw set-list hash is `5d1d49cc20ff35b5b93bd14226d80e9298b6ab33ce086ab128fbb6bd8cb5c79a`.
  All 220 provider IDs match the raw list exactly. Series IDs/names and total
  counts match retained series bytes. Provider authority establishes this snapshot,
  including possibly planned entries; release status and official worldwide
  completeness are unreviewed. The US official expansion response was an unusable
  access challenge, not independent reconciliation. English is explicit; US
  distribution of every record is not established by an English endpoint.
- The ten staging packages were reviewed September 28 against TCGdex database
  commit `309aab7060b165925fee48573e730275dfbd737c`. Their source manifest pins
  859 source-card records and reviewed name differences. D1c verifies the manifest,
  packages and aggregate source hashes; it does not reread that source checkout.
  Gym Heroes is a September 28 REST-derived package, 132 numbered records,
  raw-source hash `9d19156dc3b163b94957f52fe1a9d18ab2c42aa1c12945ff8d0a9fbf0d56a7aa`;
  that raw response is not reverified here, so its hash remains a historical claim.
- English 151 is the October 4 local-date D1/E1b reviewed package (UTC card
  requests cross into October 5). Its package SHA-256 is
  `250d0c61aea496d0854c831f62edb1030e1cd3acf91db59d239185528401a45f`.
  All retained detail/index hashes are rechecked against `retained-hashes.json`.
  The official checklist hash is
  `c74538017d7e9dca9252348e922d83affa2cb654f225421a60b41ab19188af71`.
  D5a's retained erratum applies: the checklist has no parallel-set columns;
  177 extra-variant relationships remain unknown.
- The official Singapore registry supports 1,025 canonical species, independently
  of printing and booster coverage. Artwork, rules text, provider prices and image
  permissions are excluded from normalized catalog coverage. MIT metadata authority
  does not grant those rights. No other-language coverage is asserted.

## Reconciliation method and exact coverage

[Per-set rows](../evidence/d1c-20261005/per-set.json) account for every entry exactly
once, retaining provider, language, exact set code, name, supported series, expected
count, reviewed/imported counts, numbered IDs, variant IDs, eligibility, membership,
publication evidence and gaps. [Exact gaps](../evidence/d1c-20261005/gaps.json) and the [dated missing-set list](../evidence/d1c-20261005/missing-physical-sets.md) include
all 193 absent physical IDs and names through their per-set rows, all 15 digital
exclusions, and all 177 individually identified unresolved 151 variants.

Join by `tcgdex` / `en` / provider set code and printing external ID. The ten explicit
`reconcile_legacy_set` mappings preserve legacy identities; deterministic collection
set IDs join to E6a's retained goal publication references. Names are labels, never
join authority. English 151's `sv03-5` collection key maps explicitly to provider
`sv03.5` through the reviewed bridge. Set metadata rows in the 220-expansion package
provide **zero printing coverage**. Repeated publications and the foundation's old
Scyther record coalesce by exact identity; neither adds a second printing.

| Measure | Result |
|---|---:|
| Retained universe entries | 220 |
| Provider-classified physical / digital | 205 / 15 |
| Complete reviewed numbered-card sets / partial / conflicted | 12 / 0 / 0 |
| Absent physical / digital printing sets | 193 / 15 |
| Physical expected provider card total / reviewed numbered / gap | 21,484 / 1,198 / 20,286 |
| Digital expected provider card total / reviewed / gap | 2,480 / 0 / 2,480 |
| Combined expected / reviewed / gap | 23,964 / 1,198 / 22,766 |
| Reviewed catalog records in historical synthetic publication scope | 1,375 |
| Independently supported standard booster variant rows | 207 |
| Individually unresolved 151 variant membership/issue relationships | 177 |

The 1,198 reviewed numbered identities comprise 991 older package entries and
207 151 numbers. The 1,375 catalog records comprise those 991 entries and 384 151
variants. These totals describe this **deduplicated retained reconciliation scope**,
not installed-owner coverage or full physical-variant completeness. Legacy finish,
edition and variant relationships are unknown; no foil/first-edition coverage is
inferred from a numbered row. Every covered set remains partial or unknown for
physical variants. All expected variant counts remain null. No expected numbered
count is null in this retained snapshot; future unknown counts must remain null.

English 151 has 185 numbered Pokémon, 21 Trainers and one Energy; its variants
include 346 Pokémon, 36 Trainer and two Energy records. Species mapping resolves
151 species, not 207 or 384. Older package `dex_eligible` counts retain the legacy
narrow policy, including excluded named/Dark forms; these are not broad Original
151 eligibility counts. Gym Heroes has no per-card species metadata in its source
package, so that per-set eligible count remains unknown here. E2a's separately
supported broad-goal count is 823 qualifying printings across 151 species in its
synthetic scope; do not derive it by summing the legacy flags.

Publication evidence: E6a `rehearsal-final/version-1.json` retains exact collection
set IDs, import IDs and source versions for the 11 older packages. D1/E1b
`rehearsal-evidence-3/report.json` demonstrates all 384 151 printing-to-collection
bridge identities; `publication-mapping.json` and `preservation.json` retain review,
publication/rollback/recovery behavior. Their hashes are pinned in inputs.json.
These are historical **synthetic rehearsals**, not owner installation journals or
separate-person source acceptance. No owner database was consulted.

Promo/special classifications are conservative triage: retained provider medium
is physical/digital; name labels mark promos, known product/subset labels mark
special rows, and remaining physical product classifications stay unresolved.
These labels do not assert booster membership. The rows yield 15 digital entries, 12 physical promo labels, 60 physical special
product/subset labels and 133 physical entries with unresolved product class. Pocket entries are digital even when their names contain
“Promos.” Special products remain in the physical universe and its gaps.

No duplicate numbered IDs, universe ID conflicts, language/set conflicts or
unmatched real import packages were found. `synthetic-orbits.json` (`demo-one`,
English) is unmatched and explicitly excluded. Original `config/catalog/*.json`
legacy references are not additive imports. Synthetic correction/replay fixtures,
products, observations and ownership records are outside this set reconciliation.
Historical three reviewed name differences remain accepted descriptive differences,
not identity remaps. Any conflicting future join must stop only that set/printing
and exclude it from confirmed coverage while unrelated rows continue.

For uncovered sets the retained universe provides counts, not card lists. Exact
missing printing IDs are **unknown**, never generated as `1..N`. The exact missing
set IDs and count gaps are available; claiming a complete per-card missing list
for those sets would exceed the retained evidence.

## Era/series summary

The following table is derived from per-set rows; series are provider groupings,
not an independently verified chronological era taxonomy. [JSON summary](../evidence/d1c-20261005/series-summary.json)
also enumerates the exact absent IDs in each series.

| Series | Physical / digital sets | Complete numbered / absent | Reviewed numbers / count gap |
|---|---:|---:|---:|
| Base (`base`) | 7 / 0 | 6 / 1 | 494 / 7 |
| Black & White (`bw`) | 14 / 0 | 0 / 14 | 0 / 1462 |
| Call of Legends (`col`) | 1 / 0 | 0 / 1 | 0 / 106 |
| Diamond & Pearl (`dp`) | 8 / 0 | 0 / 8 | 0 / 900 |
| E-Card (`ecard`) | 5 / 0 | 0 / 5 | 0 / 552 |
| EX (`ex`) | 18 / 0 | 0 / 18 | 0 / 1727 |
| Gym (`gym`) | 2 / 0 | 1 / 1 | 132 / 132 |
| HeartGold & SoulSilver (`hgss`) | 5 / 0 | 0 / 5 | 0 / 439 |
| Legendary Collection (`lc`) | 1 / 0 | 0 / 1 | 0 / 110 |
| McDonald's Collection (`mc`) | 12 / 0 | 0 / 12 | 0 / 166 |
| Mega Evolution (`me`) | 10 / 0 | 0 / 10 | 0 / 1264 |
| Miscellaneous (`misc`) | 2 / 0 | 0 / 2 | 0 / 161 |
| Neo (`neo`) | 5 / 0 | 4 / 1 | 365 / 18 |
| Platinum (`pl`) | 5 / 0 | 0 / 5 | 0 / 533 |
| POP (`pop`) | 10 / 0 | 0 / 10 | 0 / 193 |
| Sun & Moon (`sm`) | 18 / 0 | 0 / 18 | 0 / 2917 |
| Scarlet & Violet (`sv`) | 19 / 0 | 1 / 18 | 207 / 3505 |
| Sword & Shield (`swsh`) | 26 / 0 | 0 / 26 | 0 / 3675 |
| Pokémon TCG Pocket (`tcgp`) | 0 / 15 | 0 / 15 | 0 / 2480 |
| Trainer kits (`tk`) | 20 / 0 | 0 / 20 | 0 / 487 |
| XY (`xy`) | 17 / 0 | 0 / 17 | 0 / 1932 |

## Selected next tranche: D1d English Detective Pikachu

Select **one set: `tcgdex:en:det1`, language `en`, Detective Pikachu**, retained
series `sm` (Sun & Moon), expected **18 numbered records**. There are zero retained
reviewed/imported printing records for it. This is a small new-series expansion
candidate; it does not prove official booster distribution. Smaller metadata
entries are promo, kit, energy, sample or special-product candidates with unresolved
purpose; Southern Islands also has 18 but is in an already represented series.
The choice is “smallest useful new-series expansion candidate,” not a claim that
all smaller physical products are ineligible. Detective Pikachu's exact card/species
composition is not retained. Its name identifies an Original 151 target candidate,
but does not prove an eligible Pikachu printing. Acceptance requires actual canonical
Original 151 mappings before claiming advancement of that use case. It adds a
currently absent series to the all-era catalog if accepted; completion gain for any
account and missing-18 overlap are unknown.

Already retained exact references:

- Universe row `tcgdex:en:det1`, source-index entries `sets` and `series-sm`;
  raw `series-sm.raw` and its full SHA-256 are in source-verification.json.
- TCGdex REST v2 assessment and retained MIT license in D1/E1; set/detail source
  patterns assessed there. Proposed exact set endpoint is
  `https://api.tcgdex.net/v2/en/sets/det1`, deterministically derived from that
  assessed pattern and explicit retained ID. **No response from this URL is retained.**
- Canonical registry in `config/sealed/2026-10-04/package.json`; existing bridge,
  normalization, importer and conflict checks in D1/E1b. No Detective Pikachu
  official checklist, detail records, variant relationships or membership source
  URL is retained. No source discovery is implicit in this choice.

Executable follow-on scope (requires its own acquisition authorization):

1. Recheck HEAD and D1c candidate SHA-256 plus every listed file; preserve inherited
   edits/evidence. Read D1c, beta contract and Desktop tracker. Never operate
   `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`.
2. Budget **one provider, one English set, 19 attempts total**: one exact set
   endpoint above, then at most 18 English card-detail GETs at
   `https://api.tcgdex.net/v2/en/cards/{returned-explicit-id}`. No list endpoint,
   browsing/discovery, retries, official/retailer reads, activation or credentials.
   Sequential requests; propose 15-second per-attempt deadline, 5-minute elapsed
   acquisition ceiling and 10 MiB total retained-response ceiling. Reserve and
   consume attempts durably; errors/timeouts consume attempts. Budgets from earlier
   slices remain closed. D1c itself consumes zero of this proposed budget.
3. Stop on denial, unusable bytes, wrong language/set, provider ID drift, duplicate
   identities, unexpected count (not 18), more than 18 returned cards, exceeded
   byte/time/attempt budget or identity conflict. Retain sanitized failure evidence;
   stop the affected join. Do not substitute another set or enlarge the budget.
4. Normalize all numbered cards, category and canonical `dexId` using the retained
   1,025-species registry. Trainers/Energy get no species mappings; names/cameos
   cannot establish species. Preserve finish/edition/variant identities and raw
   variant evidence separately; provider relationships do not prove distinct US
   physical issues. Expected import is 18 numbered cards; variant record count and
   Pokémon/Original 151 count are unknown. Proposed normalization cap is 72 variant
   records; exceeding it requires a new scope, not truncation or fabricated coverage.
5. Review membership separately. With this budget no official membership source
   is acquired: keep each unsupported booster/promo/deck relationship unknown.
   Identify the exact missing official reference as the next membership blocker.
   No product, guaranteed inclusion, availability, prices, images or pull claims.
6. Validate an exact real metadata package, source hashes/rights, all 18 IDs and
   species/category mappings, explicit provider/language bridge and per-variant
   uncertainty. Require at least one supported eligible Original 151 printing;
   otherwise record that the use-case acceptance failed, without inventing mappings.
   Rehearse preview/verify/publication/idempotency/conflict/rollback on fresh
   synthetic SQLite only, with protected copies/goals/hunts/photos/reservations
   unchanged and explicit goal-update preview. Owner publication remains separate.
7. Run focused importer/bridge/goal/preservation checks and required repository
   checks appropriate to changes. Reproduce normalization offline. Update coverage
   rows, PM/roadmap/history/Desktop tracker and freeze a new candidate. Stop at
   an unmet acceptance gate; retain failed evidence. Close out source and synthetic
   evidence separately, then hand off only the exact membership blocker.

## Offline reproduction and validation

From the repository, using the retained private source/evidence paths pinned in
inputs.json (no owner root), run:

```sh
python3 scripts/reconcile_d1c.py --check
```

To regenerate only D1c derived JSON after unchanged input verification, omit
`--check`. It hashes inputs first, verifies retained universe/card sources, matches
220 unique IDs, tests explicit published-set references and 384 bridge identities,
and reconciles row/series/count totals. It never opens a database or makes a network
call. Missing retained bytes are a reproducibility blocker, not permission to fetch.
Do not regenerate the input lock to hide drift.

[Validation](history/2026-10-05-D1C-VALIDATION.md) records actual checks and the
new candidate. No full application suite is required for this offline reporting
script/doc slice. Full all-era coverage, official contents, real availability,
separate-person review, populated eBay, PostgreSQL execution, beta/owner acceptance,
hosting and release remain open.
