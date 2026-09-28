# B2 feature parity revision

September 28, 2026. The authenticated local revision restores the original collection experience alongside B2 copies, binders, goals, imports and undo. **Stop for Mike's focused review before B3.** This is engineering evidence, not owner acceptance, actual B1 owner provisioning or hosted qualification.

The repository [roadmap](ROADMAP.md) is the sequence authority. [Original app specification](../APP_SPEC.md) describes the preserved baseline; [B2 implementation](B2_IMPLEMENTATION.md) retains historical evidence. This revision started at `c26cc3f`, preserving the uncommitted owner-feedback sections in both documents. The exact tested/pushed candidate is recorded in the private handoff, rather than inserting a self-referential commit hash here.

## Parity matrix

| Original user flow | Authenticated equivalent | Verification | Remaining limits / deliberate differences |
| --- | --- | --- | --- |
| Overview: Kanto, Johto, total, printing counts | Overview, projected from active session-owned copies | Every copied species/entry matches; desktop/narrow screenshots | Physical copies and unique catalog entries are separate |
| Set summaries and rarity breakdown | Overview sets; My Cards set/type/rarity filters and owned/missing summaries | Copied 859-entry comparison; browser filters and printing details | Pinned catalog coverage, not a master-set variant claim |
| Pokédex search, region and owned/missing/unavailable filters | Pokédex with eligible-printing dialog | All 251 species memberships and ownership agree; browser search/filter/detail | Vintage normal-name exclusions retained; other cards remain collectible |
| Ownership checkboxes | Per-printing physical-copy list; add another, edit, remove | Existing B2 duplicate/revision/confirmation/undo suite and browser flows | Intentional duplicates retained; no bulk checkbox writer |
| First-edition checkbox | Explicit selection for a named physical copy, preview/confirm/undo | Duplicate/edition/value/progress/round-trip tests; browser select/undo | Unchecked means unresolved; finish/variant remain unresolved; unsupported first-edition sets rejected |
| Collection and card value scenarios | Overview conditional guide scenarios; each copy's source/date/basis under My Cards | Original copied guide totals agree exactly; missing/stale/mismatched records tests | Unresolved variants excluded from confirmed estimates. Conditional scenarios are separate, never appraisals |
| Known lots, mystery/repacks, focus and budget | Hunts, same local query planner and scorer | Pool/focus/budget checks; original saved scores agree; browser sample run | New live searches disabled; no live provider call made |
| Missing singles | Dedicated Missing singles entry and pool; current species gaps drive queries/results | Singles/filter regression and query planning; browser operability | Seller-text candidates only; no photo verification |
| Saved finds, source labels and search details | Readable private history with settings, budget and source/date | Both original searches replay; private sample/live replay checks | Live snapshots may be stale; no new search on reopen |
| Hide, explicitly reveal, reopen hidden and re-score | Session-scoped history/results and POST reveal, same inventory projection | API/DOM spoiler checks; changed-copy re-score; two-way cross-account and anonymous denial | Opaque result handles replace seller IDs; free-form condition/coverage text omitted before reveal |
| Export | Existing B2 inventory/goals/binders export | Full export/import/undo browser round trip, including edition uncertainty | Legacy backup/archive downloads remain explicit private backup tools, not hunt-result APIs |
| B2 copies, binders, goals, set batches, imports, undo | Existing Collection, Goals and Settings remain | Entire existing B2 browser script and regression suite rerun with parity enabled | Existing safe mutation limits remain |

## Implementation and semantics

`init --parity` implies B2 and refuses an existing root. It copies a B0 inventory and extracts only local guide/hunt evidence and ownership-free species names into its private `parity-evidence` directory. The authenticated database remains the only inventory authority. The original JSON, app source, frontend, hunt databases and prepared account environments are not writers or runtime sources. Existing B1/B2 roots retain their previous navigation/routes until a separately authorized migration; none is reset.

All restored private pages and APIs require the existing Django session and stable account mapping. Parity overrides B1's raw hunt endpoints with spoiler-safe projections. Direct result/reveal requests recheck the hunt owner and current inventory; admin role confers no private-data bypass. Reveal does not persist an unhidden state. Reopening clears the browser's revealed content and receives only hidden summaries. Seller IDs are replaced by opaque handles. Arbitrary seller condition text, images, links, titles, identities, raw evidence and arbitrary coverage notes are absent before reveal. Counts, price/shipping, score/evidence coverage and candidate yields retain the original permitted summary boundary. Sample reveals never contain a purchase link.

Edition is a copy-level assertion in the existing provisional identity, recorded through the same revisioned operation journal. It does not mutate shared catalog identity or other copies. Removing the assertion restores edition uncertainty; it does not assert unlimited or shadowless. Finish/variant uncertainty survives both selections and JSON round trips. Undo checks recorded after-images and cannot overwrite later edits.

Guide matching reuses the existing edition/grader/currency/source/variant-verified/date rules, including the 30-day freshness limit. Interpolated observations retain their labels and basis. There is no fallback from missing first-edition prices to standard prices. Conditional guide scenarios retain the old standard-edition hypothesis for unchecked flags **only as an explicit hypothesis**. They are excluded from confirmed variant totals. All 207 copied owner records still have unresolved details, so confirmed totals are unavailable. A missing subtotal is null, never zero. Each active physical copy contributes once to a scenario; duplicate copies multiply amounts, while set/species completion remains unique. Purchase costs stay exact and separate by currency; recorded slab grades do not select hypothetical grade scenarios.

The current copied baseline has 207 copies, one selected first edition, 133 Kanto + 20 Johto = 153 species, and two saved hunts. The legacy-equivalent raw conditional subtotal is $1,610.76 on this fresh snapshot; earlier $1,595.26 documentation belongs to an older snapshot. Matching rules were not weakened to reproduce either number.

## Evidence and review

Private evidence root: `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/`.

- `before/` and `rehearsal/`: fresh 123-file snapshot, exact migration, repeat import and byte-equal archive restoration.
- `projection/projection-report.json`: all catalog attributes, eligible-printing memberships, ownership, guide scenarios and both saved hunt scores compared with the copied original application.
- `original-browser/`: original Overview, Pokédex, My Cards, hunts, missing singles, saved finds and species dialog screenshots.
- `browser/`: full existing B2 and additional parity browser flows in independent 1280px and 390px Chromium contexts; original imported records retained unchanged.
- `clean-*` and `handoff.json`: committed-candidate checks, clean checkout and final browser evidence, exact source/tree/hash and remote privacy verification.
- `preservation.json` and `prior-environments.json`: live source/database preservation and prepared review environment hashes. No credentials or private evidence are committed.

Reproducible synthetic checks: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, and syntax checks for both beta scripts and `web/app.js`. Browser harness: `uv run --with playwright python scripts/verify_b2_browser.py --parity --root "$FRESH_PARITY_ROOT"` with that new root's server running; the harness refuses existing accounts. Copied comparison: `scripts/verify_parity_snapshot.py --root "$FRESH_COMPARISON_ROOT" --snapshot "$RESTORED_COPY"`; this also requires a new account-free verification root, never the prepared review environment.

Real iOS Safari/Android Chrome, hosted source rights, provider qualification and actual B1 owner provisioning remain separate gates. No photo scanning, live provider search, paid API, deployment, credential change, live cutover or external message occurred.

## Launch the revised review app

The new `review-local` root is prepared with copied evidence and no account credentials. Do not initialize or reset it. From the repository, choose a disposable rehearsal password at the private prompt, then run:

```sh
cd /Users/michaelfuscoletti/Desktop/dex
uv run python -m pokemon_hunter.beta.cli --root /Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local bootstrap
uv run python -m pokemon_hunter.beta.cli --root /Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local serve
```

Open `http://127.0.0.1:8011/overview/`; sign in as `admin`. If redirected to Collection after login, choose Overview. Use only one B1/B2 server on port 8011. A second bootstrap preserves the existing account/password. This rehearsal is separate from B1 actual-owner provisioning.

Mike's focused review: compare Overview/Pokédex/My Cards with the original; inspect a copy and its conditional guide evidence; preview an edition change and undo it; run/reveal/reopen sample finds; verify comfort on the narrow layout and retained collection/goals/import flows. **Wait for that feedback before B3.** Tests do not supply Mike's verdict.
