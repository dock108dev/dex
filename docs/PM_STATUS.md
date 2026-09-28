# Dex — PM checkpoint

Current B5 decision: **Mac-hosted private staging on the home network. Render setup is no longer a dependency.** [What remains to close B5](B5_DEPLOYMENT.md).

**B1 account engineering and B2 feature parity are implemented. Mike has directed continuation of pre-alpha development; B3 photo-entry and B4 catalog-expansion engineering are implemented; live recognition evaluation awaits secure API configuration. No additional B2 review approval is required. Actual B1 owner provisioning remains a separate setup item.**

## Delivered

The authenticated app restores Overview/Pokédex progress and filtering, My Cards browsing and per-copy first-edition controls, local collection/card guide scenarios, sample hunts/missing singles, and private saved-find replay with explicit spoiler-safe reveal. Existing physical copies, intentional duplicates, binders, frozen goals, imports, exports and undo remain available through the same account boundary.

The historical B2 tested runtime candidate is `f2c876b1f70ee4643df70260bd8d2d023fc583c8`, on local and remote `main` in private `dock108dev/dex`. Future work stays on `main` unless Mike requests otherwise. Subsequent documentation-only commits do not change that test identity.

## Historical B2 evidence and limits

- 158 tests passed, with clean-checkout verification, lint/format/syntax checks and GitHub CI. One pre-existing Starlette TestClient deprecation warning remains.
- Desktop and narrow Chromium flows passed, with inspected screenshots, account isolation and API/browser spoiler checks. These are not real iOS/Android results.
- Copied projections agreed across 859 entries and 251 species: 207 owned copies, 153 owned species and two saved hunts. Original collection, legacy app, saved hunts and prior prepared environments were preserved.
- Unknown variants remain excluded from confirmed values; dated guide scenarios are explicitly conditional. Purchase costs and recorded grades remain separate.
- The review app uses copied data and a disposable account. Actual B1 owner provisioning, live cutover, deployment, paid APIs and new live search have not occurred. Hosted source rights, provider qualification and real-device acceptance remain open.

## Next steps

| Owner | Next action | Boundary |
| --- | --- | --- |
| Mike / engineer | Configure the server API key when available and run a small representative recognition evaluation | Local photo/manual/fixture flow is operable; no hosted or real-recognition qualification is inferred |
| Mike, then engineer | Securely provision the actual B1 owner and verify binding/preservation when convenient | Independent setup item, not a B3 engineering blocker; preserve existing credentials |
| Engineer | Configure the Mac HTTPS endpoint and complete the operational observations | Reuse the pinned synthetic setup and passing evidence; preserve review apps and owner data |
| Mike / engineer | Make iOS/Android phones and an independent backup destination available; coordinate a Mac restart check | Actual observations required; no routine approval checkpoint |

Mike's latest direction supersedes the earlier stop-before-B3 instruction. B3 and B4 local engineering are delivered; continue with the bounded recognition evaluation once its setup dependencies are available. Existing available recognition credentials may be integrated through secure configuration; missing credentials are a concrete setup dependency, not a reason to stop independent work. The current B5 follow-up authorizes isolated staging deployment when an existing configured target is available; purchases, public signup and owner-data cutover remain excluded.

## Current access and sources of truth

Review app: `http://127.0.0.1:8011/overview/`. The existing disposable review account is initialized; preserve its data and credentials. [Restart instructions](B2_PARITY.md#launch-the-revised-review-app) apply only if the server stops.

[Authoritative roadmap](ROADMAP.md) · [Completed parity matrix](B2_PARITY.md) · [Passing candidate CI](https://github.com/dock108dev/dex/actions/runs/36370863538). The Desktop `dex_next_steps.md` is a pointer to these records. Detailed verification remains private under `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/`; do not move snapshots, guide inputs or credentials into Git.

## B3 local delivery

See [B3 photo entry](B3_PHOTO_ENTRY.md). Review at `http://127.0.0.1:8011/scan/` with the existing disposable login. The review environment retains the existing account and collection. Fixture recognition is visibly simulated; no real API calls or measured recognition accuracy/cost. Current runtime identity and verification supersede the historical B2 candidate above and are retained in `/Users/michaelfuscoletti/dex-private/b3-photo-20260928/handoff.json`.

B3 tested runtime: `a456ab7fcc3db5c22860c8d90d217196309b1ce2`; 173 tests in working and clean checkouts, lint/format/syntax checks, complete B2 parity and B3 desktop/narrow browser flows passed. Source and existing review-account/inventory preservation checks passed. Real recognition, cost/latency and real-device quality remain unmeasured.

## B4 local delivery

[Catalog expansion](B4_CATALOG_EXPANSION.md) adds private support requests, explicit evidence consent, admin triage/merge, versioned preview/verify/publish/rollback and retry-safe resolution of the existing copy. English Gym Heroes adds 132 TCGdex metadata entries through the ordinary importer. A synthetic second-game package exercises the same paths without Pokémon species requirements. No images or prices are imported.

Review: `http://127.0.0.1:8011/requests/`; the existing owner-role review login can open Catalog review. Actual owner provisioning remains separate. Real B3 recognition is still unmeasured (zero API calls); B5 deployment and live cutover are outside this delivery. The current candidate and private evidence are recorded in `/Users/michaelfuscoletti/dex-private/b4-catalog-20260928/handoff.json`.

B4 tested runtime: `9dc074d8d05ed94f88a6c278502b30d5ae9dc424`. All 188 tests passed in working and clean checkouts, along with lint/format and full B2/B3/B4 desktop/narrow browser verification. Source/review preservation passed, including unchanged credentials and spend reservations. These results establish local engineering delivery, not real recognition, actual-owner or hosted acceptance.


## Historical B5 operational foundation

[Runnable staging package and operator runbook](B5_OPERATIONS.md) delivered on local/remote main. Django + Render web/worker + managed PostgreSQL 17 is the single selected path; private photos are transactionally stored with the database for this small pre-alpha. Copied migration/restore, restart/recovery, HTTPS/session isolation, privacy erasure, retention, feedback and spending limits are locally exercised. Full candidate identity and evidence remain private under `/Users/michaelfuscoletti/dex-private/b5-20260928/`.

The original collection and review credentials remain intact. B4 evidence stays bound to `9dc074d`/`5bf44b9`. Staging source gates disable unsupported metadata/artwork/pricing redistribution while retaining private records and manual use. Estimated infrastructure is $21.50/month plus variable charges, not purchased. Zero real recognition calls; secure API key and consented evaluation photos remain dependencies.

**Next actor: operator/engineer** for the exact isolated Render account/target, HTTPS origin, database, private registry and shared secrets listed in the runbook; then actual hosted restore/restart/isolation and iOS/Android observations. B5 remains open until those exist. No purchase, public deployment, invitations or live collection cutover was performed or implied by local test results.


## Historical B5 deployment preparation follow-up

Starting at `9b7e1a1`, runtime `0f17cc9ff337ee1ce90cdb32875afd7de6d03e38` restores staging's original ten sets from pinned MIT-licensed TCGdex metadata through explicit ID-preserving importer reconciliation. Coverage is 991 Pokémon entries across eleven sets, plus two synthetic Orbits variants and 251 named species. Prices, artwork and guide/hunt projections remain unavailable; rarity follows the replacement source. This is not full local-app parity.

[Ready-to-apply package, exact image and minimal missing setup](B5_DEPLOYMENT.md). Linux AMD64 digest: `sha256:46facd36fc6bb15603960722bba10e015bc4189a73ef30a0208be051a6a52c8b`. Dedicated Virginia web/worker/PG17 configuration uses documented Render ingress, no invented CIDRs, and token-free recovery request URLs. Synthetic seed preparation is now the default; owner-data migration is separate. Costs remain about $21.50/month before variable charges; a same-size separate restore instance adds $7.50/month while retained. Nothing purchased or deployed.

198 tests passed in working and clean checkouts; local synthetic PostgreSQL migration, isolation and empty-target restore passed. The new fragment recovery flow passed local Chromium, including token-free request URLs. These are local observations only. Actual hosted/provider restore/restart and iOS/Android observations remain **not run**. Real recognition remains **0 calls / $0**, with accuracy, latency and correct/wrong/unresolved counts unmeasured. The original review app, credentials, collection and reservations are preserved.

**Next action:** operator supplies an existing authorized isolated Render target and private registry access, or owner provisions the documented paid resources; engineer deploys the pinned image and runs the hosted checklist. `OPENAI_API_KEY` + suitable consented evaluation images and actual phones are independent remaining inputs. No routine engineering approval checkpoint was added. **B5 remains OPEN; B6 has not started; actual B1 provisioning remains independent.**


## Current B5 closeout

Render login, package-registry credentials and paid resource creation are removed from the active next steps. The Mac hosts the same app, worker and PostgreSQL. Engineer next sets up trusted HTTPS for home-Wi-Fi phones, verifies the final access/security/core flows, startup/restart persistence and backup operation, then records actual iOS/Android results with Mike. Existing exact-image restore/component evidence remains valid; repeat only affected checks. See [the bounded checklist](B5_DEPLOYMENT.md).

No new runtime or deployment observation is claimed by this documentation correction. B5 remains OPEN; recognition stays simulated until B3 real evaluation succeeds; original feature limitations, actual B1 provisioning and B6 owner/pilot gates remain explicit. The historical Render notes below/above describe prior preparation only.
