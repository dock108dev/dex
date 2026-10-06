# D6 — real-source catalog and Packs data

Delivered October 5, 2026 local date (UTC acquisition October 6). Entry HEAD `16766b5c160c0bac370c1177387662646bf51b42`; handoff manifest SHA-256 `334790bd2ba9b23dae6bd790d828d9b77045e8b75152a8410f4e4f3c8f33802e`. All **1,509 entry files matched before editing**, with no unexplained drift. Inherited dirty/untracked work and historical evidence were preserved. D6 changes acquisition/normalization helpers, tests, packages, evidence and documentation; no application runtime was edited.

## Delivered data and denominators

The complete pinned TCGdex archive has **43,120 verified Git blobs**. All **24,117 data TypeScript files** parsed without executing upstream code; **23,873 card files** include other-language/digital/above-251 material retained only as raw metadata. The dated English universe has **220 sets: 205 physical and 15 digital**. Explicit single-species `dexId` and Pokémon category resolve **6,991 physical numbered #001–251 printings**, independent of collection ownership. The provider universe is a measured source snapshot, not certification of every physical release or variant ever issued.

**188 physical sets have complete source-file/English/canonical enumeration; 17 have mapping or English-field gaps.** Completeness describes provider file enumeration, not variant completeness or distribution. The exception ledger has 129 multiple/unresolved canonical records, nine absent English names and three coalesced identical variant identities. Multi-species cards remain unresolved rather than assigning one species by name. Dark, trainer-owned, regional and V/ex identities use explicit canonical mappings. Evolutions do not fill pre-evolutions.

The import batch covers **597 numbered target printings**, **1,215 newly supplied English variant identities**, and **1,347 catalog rows** including 132 retained Gym Heroes numbered rows. Of those original Gym Heroes rows, 91 now map to canonical Pokémon and 41 remain properly classified Trainer/Energy. Thus 1,306 supplied/corrected target rows is a different denominator from 1,215 new variants. The nine-set M2 checkpoint batch adds nine sets; Gym Heroes uses standalone correction to preserve all old non-target rows. Together with 13 inherited sets, the disposable state assesses 22 sets. Earlier whole-set estimates are superseded by these measured target counts.

| Set | Primary provider code | Numbered target printings | New supplied English variants |
| --- | --- | ---: | ---: |
| Gym Heroes | `gym1` | 91 | 185 |
| Gym Challenge | `gym2` | 95 | 191 |
| HeartGold SoulSilver | `hgss1` | 99 | 214 |
| Stellar Crown | `sv07` | 29 | 55 |
| Prismatic Evolutions | `sv08.5` | 40 | 128 |
| Surging Sparks | `sv08` | 38 | 69 |
| Journey Together | `sv09` | 35 | 74 |
| Destined Rivals | `sv10` | 92 | 172 |
| Crown Zenith | `swsh12.5` | 27 | 48 |
| Evolving Skies | `swsh7` | 51 | 79 |

D6 v2 excludes **13 German-only HGSS snowflake variants**. Across the full raw target sidecar, 21 language-inapplicable/unresolved variants and 58 legacy non-object variant shapes remain separately retained in `variant-exclusions.json`; no physical attributes are guessed from legacy flags. English source language does not establish US release applicability for every stamped/promo variant. Raw variant metadata, including third-party identifiers, remains retained; semantic stable variant IDs exclude mutable third-party pricing IDs. Physical variant completeness remains unknown.

## Sources, permissions and acquisition audit

Primary commit **`99c994747cf7519a3e51166cc932de79a88bd4b3`** from [TCGdex cards database](https://github.com/tcgdex/cards-database/tree/99c994747cf7519a3e51166cc932de79a88bd4b3). Archive SHA-256 **`1431e3be180cc5c8e491e480fd78b2b721155622372591d9f82bfb8aa83a6cce`**. Each archive member matches the complete, nontruncated Git tree and Git blob hash. MIT attribution is retained in `TCGDEX_LICENSE.txt`, Copyright (c) 2021 TCGdex. Card artwork was not fetched or redistributed; small repository documentation/icon assets were already embedded in the source archive and are not published card images.

Secondary commit **`39a26a144c8b6ef6c2fb17b2c29d0bb7121e3a11`** from Pokémon TCG API data: four pinned JSON files cross-check Evolving Skies, Surging Sparks, HGSS and Gym Challenge. **283 target matches, zero name/species conflicts**. Provider IDs remain distinct. The README explicitly documents public downloading, but the license endpoint returned 404 and no SPDX license was established. Secondary material is retained for inspection; normalized publishing derives from the MIT primary source. Neither provider establishes pack distribution or official contents.

The ledger is closed at `2026-10-06T03:36:31.888349+00:00` after **22.82 minutes**. Actual network downloads ended `2026-10-06T03:20:09.371607+00:00`. **36 consumed operations**: one bulk /14 metadata /11 discovery /six official /four retailer, within respective 2/20/30/40/40 limits and 132 global. Conservative response/header charge **29,631,000 bytes (28.26 MiB)**, below 250 MiB. Direct downloads enforce 30 seconds, streamed size caps, no redirects/retries and serial reads. One archive fetch is audited separately from its recorded HTTP response blocks; no Git clone transport occurred. All failed operations consumed budget. Stopped hosts remain closed.

Audit limitations are explicit: the first two search responses were not saved and their times were recorded approximately afterward. They remain consumed discovery operations; no accepted stock/content fact uses snippets. Later batched search responses are retained but their underlying provider HTTP exchanges and exact timings are not exposed. The 30 second enforcement is verified for direct downloads, not independently auditable for hosted search. Repeated shared search-response sizes are conservatively charged per query. Header/transport/body hashes and missing-body flags are in `raw-source-manifest.json`. This is collected evidence with stated limitations, not a claim of a flawless acquisition audit.

## Distribution and exact product/seller chains

The official [Crown Zenith English checklist](https://assets.pokemon.com/assets/cms2/pdf/trading-card-game/checklist/swsh125_web_cardlist_en.pdf) was retained, text-extracted and rendered. Full-page visual review of 159 numbers and the legend establishes **26 matching standard booster variant relationships across 24 species**. Only matching plain normal/holo variants use the standard black/red square markings. Reverse/blue parallel markings, stamped/jumbo/other foils and secret #160 Pikachu stay unknown in this first official review. `distribution-review.json` retains exact numbers and membership IDs. This follows the retained official standard-checklist evidence policy; it does not establish product pack quantities or guaranteed cards. D6 adds no documented promo/deck-only/guaranteed inclusions; those categories remain unknown where unresearched.

Stellar Crown is the coherent retail chain attempt. The exact Target listing **91619942**, actual static HTML, name and UPC **820650858550** establish one retail product identity: `pokemon:us:stellar-crown-bundle:820650858550`, version `US-English-2024-retailer-identity`. Contents, total/expansion-specific pack quantities and guaranteed inclusions are unknown. An unknown association to expansion `tcgdex:en:sv07` adds no documented product coverage.

The immutable observation `target:91619942:d6:20261006T031602` keeps original UTC **2026-10-06T03:16:02.472952+00:00**. Actual seller is null; direct/marketplace status unknown; item price/currency/shipping null; stock unknown. The actual response omits dynamic price/stock/seller queries (`priceSSR=false`). Generic challenge-listener scripts were conservatively flagged, then distinguished from an actual challenge during local parsing; Target remained stopped for this run. No IP-selected local store is treated as owner location or availability. Search snippets suggesting a price or availability are discovery-only and excluded.

| Attempted source | Retained result | Accepted use |
| --- | --- | --- |
| Pokémon official Stellar product gallery / expansion site | Incapsula challenge, hosts stopped | Failure evidence only |
| Official assets Stellar checklist, two distinct filenames | Both404 | No distribution inference |
| Pokémon Center exact699-85855 listing | Challenge, host stopped | Failure evidence only |
| Best Buy exact J3YSYH83TL | Transport 92 / HTTP 000, no body | Failure evidence only |
| Target91619942 |200 static exact identity, dynamic fields absent | Identity and unknown dated observation |
| GameStop412085 |403, host stopped | Failure evidence only |
| Walmart7778210362 |307 to blocked endpoint, not followed | Failure evidence only |
| Official Crown Zenith 159 checklist |200 PDF, visually reviewed |26 standard relationships |

**D6 documented products: 0; eligible current offers: 0; compatible purchasable chains: 0.** Crown Zenith has sourced standard distribution but no sourced exact sealed product. Stellar Crown has retail identity but unknown official distribution/contents and seller/stock/price. Products, packs, sellers, offers, observations and gaps are separated in `product-chains.json`. No unsupported absence is inferred from failed sources. The current missing report retains **14 Kanto / 90 total** while all 251 species, including owned targets, receive coverage rows.

## Packages and local publication

- Catalogs: `config/catalog-pipeline/d6-20261005/` (ten packages; `batch.json` has nine).
- M3 delta: `config/sealed/d6-20261005/package.json`: nine expansions / 1,030 printing records / eight catalog bridges / 26 confirmed standard booster memberships / one product identity / one unknown offer observation.
- Source universe and coverage: `evidence/d6-20261005/universe.json`, `target-printings.json`, `set-coverage.json`, `species-coverage.json`, `era-coverage.json`, `current-missing.json`.
- Stable numbered/variant/internal code relationships: `provider-mappings.json`; Git member/source hashes: `archive-file-manifest.json`; conflicts: `secondary-crosscheck.json`; prioritized gaps: `exception-queue.json`.

All referenced canonical species and inherited records are prerequisites from the retained M2 package; the rehearsal publishes those first. Source corrections preserve prior fingerprints in `sealed-correction-before.json` and `gym-heroes-correction-before.json`. D6 v1 inputs remain in validation-attempt4. `normalization-correction.json` binds before/after hashes for v2 language exclusions. Reproduction parses cached sources locally; the acquisition ledger stays closed:

```sh
.venv/bin/python scripts/prepare_d6.py
.venv/bin/python scripts/prepare_d6_sealed.py
.venv/bin/python scripts/report_d6.py
.venv/bin/python scripts/rehearse_d6.py --root /private/tmp/dex-d6-FRESH --output evidence/d6-FRESH
```

Both destination paths must be fresh; do not pre-create the rehearsal output directory. The supported order is retained M2 prerequisite → Gym Heroes standalone correction → D6 M3 delta → matching nine-set M2 checkpoint batch. M3 creates eight matching catalog children, which M2 reuses, avoiding duplicate publication. Gym Challenge stays catalog-only because the inherited sealed bridge rejects genuine first-edition values. Do not erase those values to make the bridge pass.

Existing limitations remain: M2 rejects marking target-only variant packages complete against whole-set totals; they remain partial even where the source sidecar enumeration is complete. App catalog coverage still reads the historical October 4 manifest. Two dotted source codes (`sv08.5`, `swsh12.5`) require hyphenated catalog set keys, producing two extra coverage identifiers (222 app rows versus 220 true source sets); the new universe sidecar is authoritative for D6 source counts. This is an explicit integration gap, not newly discovered sets. Current runtime coverage totals are 1,422numbered targets/2,107 published supplied variants from 22 assessments, distinct from the D6 delta counts. No runtime patch was made to broaden this data task.

## Validation, failures and preserved state

Final **validation-attempt5** uses real D6 v2 source packages on fresh disposable SQLite with a synthetic collection copied from the reconciled declarations. Existing validators/review/publication services pass; same packages return the same journal IDs. Canonical/source correction, reverse rollback and fresh reviewed republish pass. Offer publication preserves original observation time. All protected copies/photos/credentials/declarations/goals/predecessor research remain identical; all-table copied SQLite backup restoration passes. Collection remains **137/151 Kanto, 161/251 total, 14/90 missing, 286 marks**. The owner installation and 207 historical copies were not accessed or changed.

**55 focused tests pass** in `focused-tests-v2.txt`; these cover the static parser, language filtering, legacy variant shapes and relevant existing catalog/sealed/E1c services. Ruff checks pass. No full-suite/hosted/PostgreSQL result is claimed.

The actual browser shows sourced owned Vaporeon Evolving Skies V/VMAX, owned Johto Chikorita HGSS normal/reverse, and selected missing Venusaur/Scyther/Celebi. Crown Zenith Scyther confirms standard coverage; Stellar Crown/Celebi gaps and Target unknown observation stay visible. New saved research **D6 v2 sourced Kanto and Johto** reopens after server restart with an identical snapshot hash and original observation date. Two server starts, zero acquisition/provider calls during local validation. Evidence is under `browser-v2/`; the earlier v1 browser evidence remains historical. The temporary server was stopped after verification.

Retained failed attempts: attempt1 revealed first-edition sealed bridge restriction; attempt2 revealed that an already-published matching catalog bridge cannot pass the inherited verify step (resolved for D6 by ordered publication); attempt3 encountered a rehearsal assertion using incorrect lookup fields; attempt4 passed v1 before language review identified German-only variants. One attempt5 preflight refused a pre-created output path before state setup, then the proper fresh-path run passed. These attempts are retained, not used as final acceptance.

## M4 readiness and one substantial next batch

D6 catalog v2 and the limited M3 unknown/standard-distribution delta are **ready for M4 package inspection and integration**, with the retained-prerequisite/publication order above. Full M4 real shopping acceptance remains **data-blocked**: exact officially documented contents and an actual identified seller with current eligible price/stock are absent. Owner application, independent review, PostgreSQL, hosted matrix and full beta remain open. Sandbox eBay is unchanged. No source refresh may manufacture freshness for a saved observation.

One next substantial offline data batch: **Expedition 136, Aquapolis 156, Paldea Evolved 47, Twilight Masquerade 42, Astral Radiance 48, Lost Origin 51, Silver Tempest 53 =533 numbered target printings** measured from this already-retained pinned snapshot. Normalize/review those seven sets with the same English variant exclusions and exact mappings; keep raw source unchanged. No fresh network is required for that catalog work. New official-contents/current-seller acquisition requires a separate fresh authorization/source strategy; D6 closed domains and budgets must not be reopened. Resolve the coverage code aliases before treating app universe totals as current.

Final candidate: `evidence/d6-20261005/candidate.json` and `candidate.sha256`. The manifest binds the final files, inherited candidate, changed documentation and Desktop tracker. Its own bytes/hash are deliberately outside its file list.
