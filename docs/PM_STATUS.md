# Dex — PM checkpoint

September 28, 2026 UTC (September 27 evening, America/New_York).

**B2 feature parity is implemented and technically verified. The local review app is running; Mike's initial response was “great”. Focused review closeout remains pending before B3.**

## Delivered

The authenticated app restores Overview/Pokédex progress and filtering, My Cards browsing and per-copy first-edition controls, local collection/card guide scenarios, sample hunts/missing singles, and private saved-find replay with explicit spoiler-safe reveal. Existing physical copies, intentional duplicates, binders, frozen goals, imports, exports and undo remain available through the same account boundary.

The tested runtime candidate is `f2c876b1f70ee4643df70260bd8d2d023fc583c8`, on local and remote `main` in private `dock108dev/dex`. Future work stays on `main` unless Mike requests otherwise. Subsequent documentation-only commits do not change that test identity.

## Evidence and limits

- 158 tests passed, with clean-checkout verification, lint/format/syntax checks and GitHub CI. One pre-existing Starlette TestClient deprecation warning remains.
- Desktop and narrow Chromium flows passed, with inspected screenshots, account isolation and API/browser spoiler checks. These are not real iOS/Android results.
- Copied projections agreed across 859 entries and 251 species: 207 owned copies, 153 owned species and two saved hunts. Original collection, legacy app, saved hunts and prior prepared environments were preserved.
- Unknown variants remain excluded from confirmed values; dated guide scenarios are explicitly conditional. Purchase costs and recorded grades remain separate.
- The review app uses copied data and a disposable account. Actual B1 owner provisioning, live cutover, deployment, paid APIs and new live search have not occurred. Hosted source rights, provider qualification and real-device acceptance remain open.

## Next steps

| Owner | Next action | Boundary |
| --- | --- | --- |
| Mike / PM | Close out the focused B2 review or provide specific remaining changes | “Great” is positive initial feedback, not a recorded verdict on every flow or a B3 start instruction |
| Engineer | Resolve focused feedback; after explicit go-ahead, implement a bounded B3 photo-entry slice | Photo confirmation must retain uncertain identities, intentional duplicates and safe undo; paid/live API use needs separate authorization and limits |
| Mike, then engineer | Securely provision the actual B1 owner and verify binding/preservation | Separate prepared environment; the disposable review login does not close this gate |
| Later stages | B4 catalog expansion, B5 hosted/source/privacy/cost/real-device qualification, then B6 pilot | No release or pilot readiness claimed |

No new defect was reported after the parity revision. No implementation, API purchase or release action is authorized by this status update.

## Current access and sources of truth

Review app: `http://127.0.0.1:8011/overview/`. The existing disposable review account is initialized; preserve its data and credentials. [Restart instructions](B2_PARITY.md#launch-the-revised-review-app) apply only if the server stops.

[Authoritative roadmap](ROADMAP.md) · [Completed parity matrix](B2_PARITY.md) · [Passing candidate CI](https://github.com/dock108dev/dex/actions/runs/36370863538). The Desktop `dex_next_steps.md` is a pointer to these records. Detailed verification remains private under `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/`; do not move snapshots, guide inputs or credentials into Git.
