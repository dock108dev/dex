# D5a — retained-evidence Scyther chain review

October 4, 2026, America/New_York. **Bounded review closed with downstream gaps.**
Codex reconstructed the chain from retained source bytes, rather than accepting
imported rows or prior judgments as proof. Prior reviews also name Codex/operator;
this is a new retained-byte reconstruction, **not separate-person review**. Full D5
and beta acceptance remain open. No new acquisition or owner-installation access.

HEAD `c106b33d6f22df8841e0fea5b0053c54864781c3` matched. The requested D3/D4a
candidate SHA-256 `a616f55bf589b6967f62bf0da3e66f34eb49c9190db1a53c20a6d7e617c036c8`
and all 281 manifest files matched. Inherited uncommitted changes were preserved.
[Machine-readable review](../evidence/d5a-20261004/chain-review.json) records each
edge's exact IDs, paths, SHA-256, supported meaning, uncertainty and verdict.

## Chain verdict

| Edge | Verdict and limit |
|---|---|
| Canonical → research | Supported: official retained Singapore base-form #123 is Scyther, `ndex:0123`. Legacy `pokedex:123` is missing; missing-18 selects it. This research seed is separate from authenticated ownership. |
| Species → printing | Supported: `tcgdex:en:sv03.5-123:normal`, English #123/165, Uncommon, nonfoil, normal. Provider `dexId [123]`, English set identity/count and official checklist agree. |
| Normal → booster expansion | Supported: `pool:en:sv03.5-123:normal` → `tcgdex:en:sv03.5`. Visual checklist #123 has the black standard-set box and uncommon diamond. This does not establish Bundle contents or pull odds. |
| Reverse → booster | Unresolved: `tcgdex:en:sv03.5-123:reverse` / `pool:en:sv03.5-123:reverse` remain separate, membership `unknown`. Provider variant description is not distribution proof. |
| Expansion → Bundle | Retailer-described association only: `upc:820650853210:us:en:2023`, version `2023-US-English-single-bundle`, pack association `…:packs`, quantity null. Target identifies 151 packs and a September 2023 street date. English/version designation is retained normalization; these bytes lack an explicit English-language SKU label. Official exact contents remain unresolved. |
| Bundle → Target | Supported retailer identity: UPC `820650853210`, TCIN `88897904`, DPCI `087-12-7190`; `target:88897904:seller-unknown`. Recommendations excluded. Actual seller/direct-versus-marketplace is unknown. |
| Frozen goal → Packs | Synthetic implementation evidence: exact normal/reverse bridge IDs and frozen catalog journal hashes are retained in `rehearsal/goal-joins.json`. Version 1 retains no modern booster match; explicit version 2 shows one possible Scyther species. This is not owner missing-18 evidence. |

Official checklist SHA-256: `c74538017d7e9dca9252348e922d83affa2cb654f225421a60b41ab19188af71`.
Scyther detail SHA-256: `3ed928ee0cd6f6fe8f7ae07d0d4ea53762b8f2048e0fa2b5265d4c489fcead28`.
All cited raw source hashes were independently matched. Raw provider responses
remain private; excluded artwork, rules and third-party prices were not republished.

## Three immutable Target observations

All attach to the seller-unknown offer above; shipping is null in each.

| Observation suffix | Original checked time UTC | Values and timestamp quality |
|---|---|---|
| `:20261004` | `2026-10-04T22:57:28.606483+00:00` | Stock/price unknown. Retained HTTP-response timestamp; serialization precision is not backend inventory freshness. Source `target`, hash `7563c199bc8f3cc641094d339278fcad212316be19795b352eaf8366f3065b62`. |
| `:e1b-check` | `2026-10-05T00:51:59.610643+00:00` | USD 27.99, out-of-stock. Approximate original read, bounded by subsequent checklist extraction. Source `target:e1b-check`, hash `bf572141ff8cdfe20acbc3084df97450bf4d1442e8c8d7824a4f626c1ad10462`. Retained structured extraction has line references, but lacks the original returned page/HTML. Later evidence corroborates values, not this time. |
| `:d3-d4a-20261005T025427Z` | `2026-10-05T02:54:27+00:00` | USD 27.99, out-of-stock. Invocation bracket 02:54:27–02:54:28 at second precision. Source `d3-d4a:target`, hash `6cc67de5d5821e40e3965d027b33f1c2e2b7112c9ef2a69ea62b5c418e4d0fe2`. Extraction stops at L921 of advertised 1101 lines; original HTML absent. |

Backend inventory/cache time is unknown for all three. A 24-hour display window,
“crawled today”, tool-read time and add-to-cart text do not establish current
purchasability. No observation was overwritten or refreshed.

## Reviewed corrections and unresolved claims

The historical `official-checklist` source note and D1 prose mention parallel-set
columns. **Contradicted:** the retained PDF has standard-set/standard-set-foil boxes,
no parallel columns. Original source/package bytes remain unchanged.
[Review annotation package](../config/sealed/2026-10-04-d5a/review-annotation.json)
adds `d5a:official-checklist-legend-review` and a fingerprint-bound correction to
`universe:en:151-v2` appending the visible erratum and provenance. Preview → verify →
publish, idempotency, exact rollback and fresh-version republication passed on
synthetic state. No printing, membership, identity or observation changed.

The historical `official-product` note's attribution of Bundle existence to an
“official indexed expansion” is also unsupported by its retained challenge bytes.
This review supersedes that attribution; retailer identity is separately supported.
The source note's existence is not official corroboration.

**Still unresolved:** official pack contents/quantities; guaranteed inclusions;
actual seller/direct-versus-marketplace; shipping cost; current purchasability.
Target's six-pack text stays a retailer claim. Null quantities and zero recorded
guaranteed cards mean unreviewed, not no inclusions. Official gallery/151 and
Pokémon Center failures do not supply replacement evidence. D3/D4a's four attempts,
zero retries and closed budget are unchanged.

## Verification and evidence boundary

Fresh seed `/private/tmp/dex-d5a-seed`, copied root `/private/tmp/dex-d5a-copy`;
only disposable synthetic data used. Publication and post-browser row comparisons
preserved frozen goals, owned copies, hunts, scan reservations/jobs, binders,
photos/photo bytes and all older observations. Browser bookkeeping changes are
classified separately; all other tables stayed unchanged.

46 relevant tests passed (`test_sealed_catalog`, `test_sealed_expansion`,
`test_packs`). Six framework route checks passed. Ordinary browser Scyther,
printing/reverse/contents details, erratum, expansion filter, reload and predecessor
checks passed; all three checked times persisted and provider calls were zero.
Evidence is in `evidence/d5a-20261004/`, including reviewed publication journals,
preservation, browser captures/text and test output. The first browser tab opened
before server startup and returned connection refused; a fresh tab on the running
server succeeded. Created tabs/server were closed/stopped. Application code was
unchanged, so no full-suite rerun or new hosted qualification is claimed.

Final candidate and SHA-256 companion: `../evidence/d5a-20261004/validation-final/`.
Full D5, all-era coverage, 177 variant-membership gaps, populated eBay, separate-person
review and beta/owner acceptance remain open.

## One next slice

**D5b: exact official Bundle contents qualification**, only after a separately
explicit collection authorization. Proposed finite budget: two source reads total,
one each of the retained official [Bundle gallery](https://www.pokemon.com/us/pokemon-tcg/product-gallery/scarlet-violet-151-booster-bundle)
and [Pokémon Center SKU 699-85321](https://www.pokemoncenter.com/product/699-85321/pokemon-tcg-scarlet-and-violet-151-booster-bundle),
zero retries or alternate/discovery reads. Match exact SKU/version/market/language
before asserting applicability; Pokémon Center equivalence remains unverified.
Stop each denied, unusable or identity-mismatched source and retain its gap. Seek
expansion-specific quantities and explicit guaranteed-inclusion evidence; publish
only supported corrections on a fresh synthetic copy. Seller/shipping/purchasability
need later evidence. No source collection is authorized by this D5a closeout.
