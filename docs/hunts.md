# eBay hunts

The authenticated localhost app supports explicit eBay searches with the same
Browse client as the original app. Search results are private account-scoped
snapshots. The app never buys or bids, and a listing never adds an owned card.

## Search and save

Open **Hunts** at `/hunt/` for lots or **Missing singles** at `/missing/`. Select
**Find bargains** or **Fill a collection goal**, Live eBay or Sample cards, a
search pool, optional collection goal, focus and delivered budget in USD. An
optional search phrase can direct a card or lot search. Search starts only when
you request it. Bargain searches include owned cards; goal-filling searches use
the goal's frozen checklist and your current active copies. Without a goal, the
default collection scope remains Vintage 251.

The search pools are known lots, individual cards and mystery/repacks. Default lot
and mystery searches use Pokémon query pools. Goal-targeted singles use the
selected published game, set, card name and number, including Trainer/Energy or
other game entries when present in the catalog. Focus can narrow Pokémon searches
to Kanto, Johto, missing rares or cheap bulk. A goal's game, sets, card type,
rarity and Pokédex filters come from the saved goal builder. Open a goal's missing
search to use that scope directly.

Each batch saves automatically. **Next eBay batch** continues the captured search
purpose, phrase, goal, pool, focus and budget rather than silently using changed form choices. Saved
finds at `/finds/` can be reopened without a new provider call; they are re-scored
against current ownership and spoiler reveal starts hidden again.

Titles, contents and seller links stay hidden until explicit reveal. Exact hits
from live listings are seller-text candidates, not photo-verified card identity.
Unknown and mystery contents remain unknown. Check the revealed seller page for
current availability and condition.

## Price comparisons

Results show the delivered price, guide reference, difference/discount, evidence
basis, priced-card coverage and source dates. **All search results** preserves
results without guide coverage. **Below guide reference** filters the saved
results without calling eBay again. A low price against a benchmark needs seller
review; it is not an established bargain or profit estimate.

Identified singles use an ungraded guide unless seller grade and grader match
supported graded evidence. Unknown edition uses a clearly conditional standard
edition assumption. General grade 7/8/9 scenarios do not silently become PSA
grade matches; the existing PriceCharting grade-10 reference supports PSA 10.

Identified lots use a conditional standard, ungraded baseline. A first-edition or
graded mention for one card never applies to every card in the lot. Fully priced
identified contents can be summed; partial identification/pricing shows only a
subtotal and leaves other contents unvalued. For known lots with no identified
cards, an average of current guides in the selected catalog scope times the
stated card count is shown as a **benchmark**, with its coverage. It does not
predict the contents or appraise that listing. Mystery, sealed and unopened
unknown contents do not receive this benchmark.

Reference values require current, nonnegative, finite USD evidence from a valid
HTTPS source and a date no older than 30 days. Comparisons use retained guides and
explicitly refreshed project `config/market_values.json` snapshots, selecting the
newest valid observation. An equal-date refreshed snapshot takes precedence.
Searching does not refresh guides. Per-card identities and guide links appear
only after reveal. Auction comparisons use the current bid, which can change;
it is not a settled purchase price. Tax, fees and resale proceeds are not modeled.

## Local provider settings

Local setup status, October 3, 2026: Sandbox is selected and the current private
App ID has a Sandbox marker. Both required credentials are present; the running
server has no eBay credential overrides. Sandbox authentication and Browse succeeded
with zero listings. Production setup is blocked by the disabled keyset described
below. The earlier Production failure was OAuth HTTP 401 (`invalid_client`).
Dev ID is not used by this app.

Set `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` in the server environment or private
checkout `.env`, using `.env.example` for key names. Never paste credentials into
chat or commit them. Server environment values take precedence. The authenticated
app reads only these credentials and optional `EBAY_DELIVERY_POSTAL_CODE` from
`.env`; recognition and webhook keys are not loaded.

`config/settings.yaml` selects production or sandbox, marketplace and delivery
destination. Sandbox status is labeled and does not establish real offer
availability. The page reports configuration status without exposing credentials.
Configured credentials alone do not prove successful eBay access. Live hunts are
available only in the local profile.

## Coverage and evidence limits

A batch runs at most eight planned queries, with at most two provider pages per
query and buying option. Coverage shows the executed portion and whether provider
warnings limited results. Longer plans can continue in another explicit batch.

Delivered budget uses known item price plus known shipping and excludes tax.
Listings marked unavailable or lacking sufficient price/shipping information
are excluded from results. Prices and availability can change after a search.
Recommended bids remain unavailable when condition, complete contents or sourced
raw-price evidence is missing. A guide comparison or benchmark does not establish
those inputs.

Provider failures show a safe error and require an explicit retry. They do not
silently substitute sample results. Local simulated-provider tests qualify the
application behavior; actual eBay access and Mike's personal-use review remain
separate checks.

Current local environment after Mike's October 3 follow-up is Sandbox. Credentials
were updated privately; the explicit narrow Pikachu search authenticated and
completed Browse successfully with zero listings. Saved/reopened Sandbox results
are test evidence. Production setup and populated-result review remain pending.

## Production setup gate: October 3, 2026

Setup audit base: `ca4dde5baa18fa05f7c0a48bd9e175886ba628ac` on local main;
application source remains `17306fee355091bed082527bee02a01e26cf4f01`.
After Mike signed into the developer portal privately, Application Keys showed
**Your keyset is currently disabled** for the dex Production keyset, with links
to account-deletion compliance or exemption. In its Production notification page,
Marketplace Account Deletion is selected, exemption is off, an alert email is
present, endpoint and verification token are empty, and Send Test Notification
is disabled. No external settings or credentials were changed.

The current `.env` contains one Sandbox-marked App ID and secret, without obvious
placeholder or whitespace problems. The supported running server uses the expected
private root and has no eBay credential overrides. This confirms the current
Sandbox pairing; it does not verify a Production pair or prove which credentials
were used in the earlier failed attempt. No new OAuth or Browse call was made.
Do not switch only the environment to Production with these Sandbox credentials.

Official eBay requirements, checked October 3:

- [OAuth credentials](https://developer.ebay.com/api-docs/static/oauth-credentials.html)
  are application- and environment-specific. Use App ID and Cert ID from the same
  active Production keyset. The existing client uses HTTP Basic authentication,
  `client_credentials` and the base API scope on the selected environment's token
  endpoint; [Browse uses an Application token](https://developer.ebay.com/develop/api/buy/browse_api).
  A member-consent flow or RuName is not used for this search.
- [Account-deletion notifications](https://developer.ebay.com/develop/guides/sell/marketplace-user-account-deletion)
  must be configured, or a valid exemption obtained, before a new keyset is active.
  The documented exemption is for applications not persisting any eBay data.
  Dex saves the raw listing response in `saved_hunts.raw`, including any seller
  data returned, so its saved-snapshot workflow cannot truthfully claim that.
- The notification endpoint must be public HTTPS, support the challenge GET and
  notification POST, validate notifications and process applicable deletions.
  A localhost URL or a handler that only acknowledges requests is insufficient.
  No such handler is implemented in this localhost app. Hosting remains deferred;
  enabling this path needs a separately scoped callback service and data handling.
- [Buy API Production requirements](https://developer.ebay.com/api-docs/buy/static/buy-requirements.html)
  describe separate business-use approval/access. Active OAuth credentials alone
  do not establish Browse entitlement; the account's approval has not been verified.

**Exact external settings:** open
[Application Keys](https://developer.ebay.com/my/keys), select dex under Production,
then [Notifications](https://developer.ebay.com/my/push/?env=production&index=0).
Keep Marketplace Account Deletion selected. A compliant callback would need its
real HTTPS URL in **Marketplace account deletion notification endpoint** and a
private 32–80 character verification token (letters, numbers, `_`, `-`), followed
by **Save**, successful challenge validation and **Send Test Notification**.
The existing alert email can remain. Do not enable the non-persistence exemption
for the current app or supply an invented endpoint. No callback is available now.

**Mike's next action:** open
[eBay Developer Technical Support](https://developer.ebay.com/my/support/tickets)
and ask for the supported Production activation/access path for dex: a personal,
read-only Browse app that saves listing snapshots on localhost, whose Production
keyset is disabled for account-deletion compliance. Ask whether any applicable
exemption exists for this actual data flow, or a callback is required, and whether
Browse Production approval is already present. Share no Cert ID or tokens. This
is an owner action; no ticket was submitted by the agent. If a callback is required,
resolve its separate hosting/data-handling scope before activation. Once activated,
privately preserve the Sandbox pair, install the matching Production App ID/Cert ID
in `.env`, and select `environment: production`; check server overrides first.

**One queued pass, not executed:** authenticated `/missing/`, Live eBay,
Find bargains, individual cards, query `pokemon base set`, All focus, no goal,
default Vintage 251 scope, $100 delivered ceiling (item/current bid + known
shipping, before tax), EBAY_US/USD, existing US delivery destination. One query,
100 items per page, at most two pages for each of AUCTION and FIXED_PRICE: at most
four search-page requests before the existing bounded transport retries, at most
400 raw rows before deduplication. The eight-query batch cap remains unchanged.
No Next eBay batch, repeat search, automatic guide refresh or sample substitution.
Record actual counts and provider warnings; current count is **unavailable because
the pass did not run**, not zero.

On populated results, retain delivered-price arithmetic and source evidence,
verify dated guides and identity/edition/grade assumptions, explicitly reveal and
review seller links, then save/reopen and confirm spoilers reset. Missing guides
stay unavailable. Reopening and comparison filtering must reuse the snapshot
without new provider requests. Empty/provider-failure outcomes stop the pass and
retain sanitized evidence. Populated comparison/reveal/seller/spoiler checks and
Mike's personal-use acceptance remain open.

The supported private-root check passes. This is a documentation/setup audit,
with no application or provider configuration changes; the prior 328-test result
remains tied to unchanged application source. Preservation fingerprints and
sanitized portal-status evidence are retained privately under
`/Users/michaelfuscoletti/dex-private/ebay-production-setup-20261003`, outside Git.
