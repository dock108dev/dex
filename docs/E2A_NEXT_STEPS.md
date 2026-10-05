# Pokédex — beta next steps

Updated October 4, 2026. **Data collection and engineering are required beta work.**
Collect the original 151 using qualifying cards from any era; expand the underlying
TCG catalog across eras and species, retain classic eBay hunting and add a current
sealed-product index for missing Pokémon.

[Roadmap](dex/docs/ROADMAP.md) · [Required beta contract](dex/docs/BETA_REQUIREMENTS.md) ·
[PM status](dex/docs/PM_STATUS.md) · [Catalogs](dex/docs/catalogs.md) ·
[eBay access](dex/docs/hunts.md#production-access)

## Current baseline

Repository: `/Users/michaelfuscoletti/Desktop/dex`.
Observed HEAD: `fba1be13135b0b3bbb6cb674de5586e0f3c80740`.
Preserve the October 4 planning changes and recheck HEAD/diff before implementation.
No new application-test, remote-sync or live-stock claim follows from these edits.
Current source has local authenticated collection/goals and eBay hunts. The E1
public species registry contains 1,025 species; legacy goals retain #251. E2a broad goal implementation is delivered with qualification pending; the shopping UI remains outstanding. The original-app ledger shows 133/151, missing 18; authenticated
ownership is separate and must be reconciled before the owner walkthrough.

## Next action: E2a qualification — explicit goal versions

Read [E2a closeout](dex/docs/E2A.md) and [dated validation](dex/docs/history/2026-10-04-E2A-VALIDATION.md).
Implementation is delivered, but E2a acceptance is partial. The restricted execution
runtime denied localhost socket binding and browser access; ordinary UI captures
remain absent. Locked sync hit a macOS runtime panic; three existing cleanup tests
cannot invoke `ps`. No full E2 or beta completion is claimed.

The new `original-151-reviewed-v1` policy freezes 151 canonical slots, reviewed
published memberships, catalog package references and retained goal lineage.
Special/named/regional Pokémon can count; Trainer/Energy/cameo/unresolved identities
cannot. Progress uses only active resolved copies of the authenticated account.
The copied rehearsal has 823 qualifying printings / 151 covered species and 0/151
resolved ownership; the research seed never supplies ownership. Explicit successors
show membership/policy/progress changes, retain predecessors and reject stale or
repeated confirmations. Current ownership is separate from saved frozen hunt scope.

Exact final candidate and SHA-256 companion:
`dex/evidence/e2a-20261004/validation-final/candidate.json` and `candidate.sha256`.
Verify HEAD, current diff and every listed hash before continuation. Preserve all
E1/E1b/E2a changes. Detailed results and copied-state table hashes are retained under
`dex/evidence/e2a-20261004/`. No E2a schema migration was needed.

Execute one bounded engineering qualification slice:

1. Use the exact frozen candidate and disposable copied root
   `/private/tmp/dex-e2a-20261005-copied-qualified`; re-create fresh synthetic state
   using the closeout scripts if that temporary root is unavailable.
2. In a runtime permitting localhost binding/browser access, start the closeout's
   127.0.0.1:8012 server command. Never use or restart the owner installation.
3. In a fresh authenticated synthetic session, create the broad goal, inspect
   policy/versions/151 checklist/coverage/account progress, confirm, inspect missing
   species, preview and cancel an update, confirm a fresh successor and reopen both
   retained versions. Save captures and assert actual UI state; click no live search.
4. Verify sample search/reopen/filter retains its captured goal version and spoiler
   behavior while provider calls remain zero. Compare legacy goals/copies/hunts and
   reservation rows against the retained baseline.
5. Complete locked dependency sync and the three existing process-cleanup checks in
   the permitted runtime. Stop on the first failed gate; any bounded repair requires
   fresh source hashes/tests and a new frozen candidate.
6. Update E2a acceptance only from recorded results; synthetic UI evidence still
   does not establish owner acceptance. Close with one next bounded slice from the
   remaining beta requirements.

No catalog or retailer acquisition, pack-shopping UI, purchases, credentials,
Production activation, hosting, recurring jobs or owner-root writes. Keep full
all-era coverage, official contents, 177 variant membership gaps, independent
Scyther review, live providers and owner acceptance open. Full E2 remains partial.

## Required remaining work

| Track | Beta deliverable | Status |
|---|---|---|
| D1 | All-era English catalog, full species registry and coverage manifest | PARTIAL: registry/manifest delivered, all-era printings/reconciliation open |
| D2 | Species/printing/booster-set mappings | PARTIAL: 207 numbered 151 identities / 384 variants; 207 standard booster rows / 177 extra-variant membership gaps |
| D3 | Official sealed products, exact pack contents and separate guaranteed cards | PARTIAL: product identity; official contents blocked |
| D4 | Retailer access assessment and dated offers | PARTIAL: Target unknown and dated extracted out-of-stock observations; seller/shipping unknown |
| D5 | Reviewed missing-18 coverage, Scyther traced end to end | PARTIAL: every row has normalized printing/standard-booster links; downstream chain gaps remain |
| E1 | Schema, validated imports, provenance and coverage reporting | Reviewed bridge/descriptive correction delivered; broader/browser E1 and data gates partial |
| E2 | Broad goals, canonical eligibility and explicit goal updates | E2a implemented; browser/runtime qualification pending; full all-era coverage open |
| E3 | Species/whole-goal pack finder and missing-species coverage comparison | TODO |
| E4 | Bounded offer refresh, stock/freshness/price filters and purchase links | TODO |
| E5 | Saved pack research and retained classic eBay loop | TODO |
| E6 | Integrated local, live-source and owner acceptance | TODO; eBay gate blocked |

D2–D4 research can progress alongside E1–E2 after the record schema is agreed.
Complete the catalog requirement as well as the missing-18 path: 151 is the owner's
goal, not the catalog ceiling. Research Pokémon Center US and direct-sold Target,
Walmart, Best Buy and GameStop offers, recording supported access and gaps.
These targets are not verified stock or promised integrations.

## Retained eBay owner action

The following records October 3 observations, not a new portal verification.
Recheck before another live attempt. It does not block catalog/product engineering.

**Production outcome: blocked before any new attempt.** After Mike signed in
privately, eBay Application Keys showed the dex Production keyset **disabled**
pending marketplace account-deletion compliance. On its Production Notifications
page, Marketplace Account Deletion is selected, exemption is off, alert email is
present, endpoint/token are empty, and Send Test Notification is disabled.
No portal setting or credential was changed. This proves the current activation
blocker, not the historical cause of OAuth HTTP 401 (`invalid_client`). Production
Browse entitlement remains unknown.

Current `.env` has one privately checked Sandbox-marked App ID/secret pair;
`config/settings.yaml` selects Sandbox. The running supported server uses the
expected private root with no eBay credential overrides. Keep this working pair
and configuration intact until a matching active Production pair is available.

Dex saves raw eBay responses in account-scoped snapshots. The official documented
non-persistence exemption does not fit that data flow. eBay requires a real public
HTTPS callback to validate the challenge, receive verified notifications and
process applicable deletions. The localhost app has no such handler. Hosting
remains deferred; no fabricated endpoint or acknowledge-only implementation was
added. A supported alternative must be confirmed by eBay, or the callback needs
separately scoped hosting and data handling.

**One concrete next action for Mike:** open
[eBay Developer Technical Support](https://developer.ebay.com/my/support/tickets)
and ask for the Production activation/access path for dex: personal read-only
Browse on localhost, with saved listing snapshots and a Production keyset disabled
for account-deletion compliance. Ask whether an applicable exemption exists for
this actual data flow or a callback is required, and whether Browse Production
approval is already present. Share no Cert ID or tokens. No ticket has been sent.
See [retained provider observations](dex/docs/history/2026-10-03-VERIFICATION.md)
for the dated evidence and source references.

After access and credential pairing are resolved, qualify one explicit bounded
classic search through comparison, reveal, seller review, save and reopen. Stop
on empty results/provider failure and retain sanitized evidence. Do not repeat
until populated or substitute samples. Reopening/filtering make no provider calls.
Broad-goal searches require their own scope evidence after E2.

Prior Sandbox authentication returned zero listings: empty saved reopening and
isolated replay cannot qualify populated Production behavior. Historical evidence
remains at `/Users/michaelfuscoletti/dex-private/ebay-production-setup-20261003`.

## Beta acceptance and preservation

All six gates in `docs/BETA_REQUIREMENTS.md` are required. Data collection,
engineering, real purchasable offers, populated eBay and Mike's walkthrough are
separate evidence classes. Source membership does not establish stock; coverage
does not predict pulls. A documented unavailable product is a valid data result;
an unresearched gap is unfinished work. No purchases or bids during qualification.

Existing private root:
`/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local`.
Preserve database, photos, secrets, goals, hunts, source evidence and spending
reservations. Do not reseed or use the owner's installation for development.
Hosting, LAN/phone access, managed startup and invited users remain separate work.
