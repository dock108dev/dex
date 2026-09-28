# Dex — local pre-alpha roadmap

Updated September 28, 2026. **Current target: Mike alone, using the existing app on localhost on his Mac.**

This is the authoritative scope and next-step record. It replaces the earlier Render and home-network B5 plans. Preserve the existing login, collection, photos, saved hunts and original app. No hosting, LAN access or phone qualification is needed now.

## Delivered and remaining

| Area | Current status | Next action |
| --- | --- | --- |
| B0 preservation | Exact copied-data migration and restoration verified | Preserve source records and ordinary local backups |
| B1 accounts | Authentication and isolation implemented; existing local login works | Keep that login; separate historical owner provisioning is not a prerequisite for local use |
| B2 collection/parity | Pokédex, progress, browsing, edition controls, local value scenarios, spoiler-safe sample hunts/history plus copies, binders, goals, imports, exports and undo delivered | Fix concrete local regressions only; no extra review-closeout gate |
| B3 photo entry | Private uploads, durable jobs, manual matching, provisional copies, confirmation/cancellation and undo delivered | Enable and evaluate real recognition; latest handoff reports no key, zero real calls and unmeasured accuracy/latency |
| B4 catalogs | Requests, consent, reviewed ingestion/publication/rollback and same-copy resolution delivered; Gym Heroes added | Maintain existing behavior; further coverage follows actual need |
| B5 infrastructure | Local staging engineering and restore evidence retained | DEFERRED: not a current completion requirement |
| B6 invited pilot | Not started | DEFERRED: Mike is the only current user |

## Immediate engineering priority

Make real photo recognition useful in the existing localhost app. Inspect only the intended server configuration for key availability without exposing secrets. If configured, use a small suitable labeled photo set and the existing spending ceilings; record correct, wrong and unresolved results, latency and cost before manual correction. If missing, give the shortest secure local setup step. Never request an API key in chat. Keep fixture results labeled simulated until real recognition is enabled.

Preserve confirmation before ownership changes, exactly-once additions, intentional duplicates, uncertain identity fields and safe undo. Do not infer grade, authenticity, condition or value from a photo. Manual entry remains available on provider failure. Preserve existing spending reservations; do not reset counters to extend evaluation.

## Local product and data rules

- Use the existing authenticated app at `http://127.0.0.1:8011/overview/`; Scan/Add is `/scan/`. These are documented endpoints, not a claim that this documentation edit checked server health.
- Preserve the working account and its data. The historical B1 owner bootstrap remains unperformed unless separately observed; it is not a blocker and must not trigger account reset, environment recreation or data migration.
- Original source data and prior environments remain intact. This scope correction does not perform a cutover or make two stores authoritative. If data divergence becomes a concrete user problem, reconcile it explicitly rather than overwriting either copy.
- Keep localhost restrictions, authentication, authorization, privacy controls, input validation, secrets handling, sensible regression checks and ordinary local backups. Git preserves source history, not excluded private data or credentials.
- The restored local experience is the baseline. Staging-only restrictions on prices, artwork and hunt projections are not automatically local restrictions. Verify any actual local gap before claiming it; retain dated sources, uncertainty, sample/live labels and spoiler boundaries. Local use does not invent source permissions or enable a new provider.
- Continue on local `main`, synced to private remote `main`. Preserve concurrent changes and inspect staged content for private data. No routine stage-approval loops.

## Deferred work

Render, registry publication, paid hosting, LAN HTTPS, device certificate installation, cross-device qualification, managed startup, Mac reboot checks, external backup infrastructure and invited-user rollout are deferred. Keep their implemented code and runbooks as optional future work; do not extend or remove them merely for this correction. No device, backup-destination or restart appointment is needed to continue the local product.

The broader 100-photo recognition benchmark and hosted/pilot acceptance matrix are future release criteria, not requirements for this small local evaluation. Defer those gates rather than falsely marking them passed. Actual measured recognition results and useful local behavior are the current outcome.

## Evidence and references

Prior results remain attached to their original candidates: B2 parity `f2c876b` (158 tests), B3 `a456ab7` (173), B4 `9dc074d` (188), B5 operational package `9b7e1a1` (193), and deployment preparation `0f17cc9` (198). These are recorded prior checks, not rerun by this PM update. `06eb032` changed documentation only. None establishes real recognition quality.

[PM status](PM_STATUS.md) · [Photo entry and secure configuration](B3_PHOTO_ENTRY.md) · [Local parity](B2_PARITY.md) · [Catalog expansion](B4_CATALOG_EXPANSION.md) · [Data/workflow contracts](BETA_DESIGN.md).

[Superseded roadmap and historical delivery records](history/2026-09-28-pre-local-scope-roadmap.md) are retained for evidence only. This page controls current priorities.
