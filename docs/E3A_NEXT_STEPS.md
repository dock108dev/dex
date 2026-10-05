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
public species registry contains 1,025 species; legacy goals retain #251. E2a broad goal implementation is locally qualified; the shopping UI remains outstanding. The original-app ledger shows 133/151, missing 18; authenticated
ownership is separate and must be reconciled before the owner walkthrough.

## Next action: qualify implemented E3a on the prepared synthetic copy

Read [E3a closeout](dex/docs/E3A.md) and
[validation](dex/docs/history/2026-10-04-E3A-VALIDATION.md).
The ordinary authenticated view is implemented with frozen/account-scoped coverage,
Scyther, product uncertainty and retained offers. Browser permission and loopback bind
were denied in the current environment; no browser walkthrough or screenshot exists.
Locked sync crashes and three ps-dependent cleanup tests remain environment-blocked.
Restore an ordinary permitted local environment, verify the final E3a manifest and
run the retained synthetic walkthrough on supported port 8011. Preserve the owner
installation and all prior evidence; stop only the disposable server you start.

One separate subsequent data slice is D3/D4a for exact US English 151 Booster Bundle
UPC 820650853210 / Target TCIN 88897904: at most two official and five retailer page
reads, seven total attempts, no retries. Exact identities, source budget, retained
evidence, review requirements and stop rules are in E3A.md. Contents, 177 variant
membership gaps, independent Scyther review, all-era acquisition, populated eBay
and owner acceptance remain open. No acquisition was performed in E3a.

## Required remaining work

| Track | Beta deliverable | Status |
|---|---|---|
| D1 | All-era English catalog, full species registry and coverage manifest | PARTIAL: registry/manifest delivered, all-era printings/reconciliation open |
| D2 | Species/printing/booster-set mappings | PARTIAL: 207 numbered 151 identities / 384 variants; 207 standard booster rows / 177 extra-variant membership gaps |
| D3 | Official sealed products, exact pack contents and separate guaranteed cards | PARTIAL: product identity; official contents blocked |
| D4 | Retailer access assessment and dated offers | PARTIAL: Target unknown and dated extracted out-of-stock observations; seller/shipping unknown |
| D5 | Reviewed missing-18 coverage, Scyther traced end to end | PARTIAL: every row has normalized printing/standard-booster links; downstream chain gaps remain |
| E1 | Schema, validated imports, provenance and coverage reporting | Reviewed bridge/descriptive correction delivered; broader/browser E1 and data gates partial |
| E2 | Broad goals, canonical eligibility and explicit goal updates | E2a locally qualified through runtime and synthetic browser walkthrough; full E2/all-era coverage open |
| E3 | Species/whole-goal pack finder and missing-species coverage comparison | E3a implemented; qualification partial; full E3 open |
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
