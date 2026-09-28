# Dex — PM checkpoint

September 28, 2026 UTC (September 27 evening, America/New_York).

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
| Later stages | B5 hosted/source/privacy/cost/real-device qualification, then B6 pilot | No release or pilot readiness claimed |

Mike's latest direction supersedes the earlier stop-before-B3 instruction. Proceed with the B3 implementation prompt. Existing available recognition credentials may be integrated through secure configuration; missing credentials are a concrete setup dependency, not a reason to stop independent work. Do not purchase services or deploy as part of this local milestone.

## Current access and sources of truth

Review app: `http://127.0.0.1:8011/overview/`. The existing disposable review account is initialized; preserve its data and credentials. [Restart instructions](B2_PARITY.md#launch-the-revised-review-app) apply only if the server stops.

[Authoritative roadmap](ROADMAP.md) · [Completed parity matrix](B2_PARITY.md) · [Passing candidate CI](https://github.com/dock108dev/dex/actions/runs/36370863538). The Desktop `dex_next_steps.md` is a pointer to these records. Detailed verification remains private under `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/`; do not move snapshots, guide inputs or credentials into Git.

## B3 local delivery

See [B3 photo entry](B3_PHOTO_ENTRY.md). Review at `http://127.0.0.1:8011/scan/` with the existing disposable login. The review environment retains the existing account and collection. Fixture recognition is visibly simulated; no real API calls or measured recognition accuracy/cost. Current runtime identity and verification supersede the historical B2 candidate above and are retained in `/Users/michaelfuscoletti/dex-private/b3-photo-20260928/handoff.json`.

B3 tested runtime: `a456ab7fcc3db5c22860c8d90d217196309b1ce2`; 173 tests in working and clean checkouts, lint/format/syntax checks, complete B2 parity and B3 desktop/narrow browser flows passed. Source and existing review-account/inventory preservation checks passed. Real recognition, cost/latency and real-device quality remain unmeasured.

## B4 local delivery

[Catalog expansion](B4_CATALOG_EXPANSION.md) adds private support requests, explicit evidence consent, admin triage/merge, versioned preview/verify/publish/rollback and retry-safe resolution of the existing copy. English Gym Heroes adds 132 TCGdex metadata entries through the ordinary importer. A synthetic second-game package exercises the same paths without Pokémon species requirements. No images or prices are imported.

Review: `http://127.0.0.1:8011/requests/`; the existing owner-role review login can open Catalog review. Actual owner provisioning remains separate. Real B3 recognition is still unmeasured (zero API calls); B5 deployment and live cutover are outside this delivery. The current candidate and private evidence are recorded in `/Users/michaelfuscoletti/dex-private/b4-catalog-20260928/handoff.json`.
