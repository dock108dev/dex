# B3 photo entry — local pre-alpha

September 28, 2026. B3 engineering is implemented in the authenticated Django app. Actual owner provisioning, hosted operation and real-device acceptance remain separate. No live collection cutover, deployment, purchase or marketplace search is included.

## Use

Open `/scan/` from Scan/Add. Choose one front and optionally one back or close-up from the camera/library, upload, review candidates, select a supported catalog entry or retain an unidentified card, enter corrections/notes, check the review acknowledgement and confirm one physical copy. Existing copies produce a warning; intentional duplicates use a new photo entry. Refresh reopens the durable job. Manual catalog entry remains available from Collection.

The local review uses **fixture mode**, prominently labeled SIMULATED. Its outcomes are deterministic catalog examples, not identification of the uploaded photo. Choose readable, ambiguous, unreadable, unsupported or failed to exercise the flow. Missing credentials do not prevent private photo storage, manual matching, provisional additions or undo.

Copy creation uses the existing revisioned collection journal, physical-copy store and derived views. The job ID is the stable confirmation identity. Retrying confirmation returns the same operation; an undone operation cannot be reapplied. Undo checks after-images and refuses to overwrite later edits. Cancellation and worker completion never create copies. Scan provenance links retained photos from Collection; edition/language/finish/variant uncertainty survives confirmation. Provisional records have no printing ID and cannot satisfy exact-printing goals or receive verified printing values. Corrections and selected identity are private evidence, never automatic catalog changes.

## Private storage and jobs

Private normalized JPEG bytes are stored in the existing owner-only SQLite database, scoped to account and job. There is no public media directory or arbitrary URL ingestion. Every image/job/action rechecks active account mapping; worker execution derives identity from its persisted job and checks it again after recognition. Response caching is disabled. Invalid content, animation, oversized files, tiny dimensions and decompression bombs are rejected. JPEG/PNG/WebP input is limited to 8 MB per image, 200px minimum, 24 megapixels maximum and 10,000px maximum dimension; images are orientation-corrected, resized to at most 1600px and re-encoded without metadata. HEIC is not supported; use a compatible camera/browser export.

A background worker started by `serve` claims database jobs outside page requests. An independent `scan-worker` command is also available; transactional claims prevent duplicate processing. States: queued, processing, needs-confirmation, needs-better-photo, unsupported, failed, cancelled, confirmed. Worker interruption after 120 seconds becomes failed, requiring explicit retry. Late results compare their claim timestamp and cannot overwrite cancelled or newer attempts. At most two provider attempts per job, with no automatic retry of possibly billed calls. Upload quota is 20 entries per user per rolling 24 hours.

Unconfirmed uploads expire after seven days. Confirmation retains them with the copy. Cancellation/undo deletes image bytes; removal blocks serving immediately and worker cleanup removes bytes. Delete retained photos is available independently of copy removal. Revoked accounts lose image access immediately and worker cleanup removes bytes. Job metadata and operation provenance remain for audit. Existing private backups may retain old bytes until an operator deletes those backups; hosted backup expiry/account erasure remains B5 work. No image sharing or training consent is inferred.

## Recognition configuration

Enable B3 in an existing **isolated B2 root** using `uv run python -m pokemon_hunter.beta.cli --root PRIVATE_ROOT enable-scans`, then restart its server. This adds tables and a marker without resetting identities, passwords, inventory or existing operations. Back up the private database before upgrading. Do not run this against the original collection.

`PRIVATE_ROOT/scan-config.json` (owner-only) supports:

```json
{"enabled": true, "mode": "openai", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5}
```

Modes are `manual` (default), `fixture` (explicit simulation), and `openai`. Set `enabled` to false to stop new uploads and worker calls; already sent API requests cannot be recalled. Manual collection entry and review of existing results remain available. Configure `OPENAI_API_KEY` securely in the server/worker environment; never put it in this file, arguments, source or logs. Restart the process after changing credentials. No key was available in the implementation process environment, and no live recognition calls were made.

Model snapshot: `gpt-4.1-mini-2025-04-14`; prompt, schema and matcher version: `dex-photo-v1`. Server-side Responses API, inline image bytes, strict JSON schema, no tools, `store: false`, maximum 600 output tokens, 5-second connect and 35-second network inactivity timeout. Model evidence is validated again locally, then matched by name and every supplied number/set/language clue against the existing catalog. Conflicting clues never silently fall back to an exact match. Candidates remain user-reviewed; the model cannot publish catalog rows or mutate ownership. Edition/finish/variant/language clues are displayed but never automatically asserted on a copy.

Each real request reserves $0.05 before transmission, transactionally across workers, against lifetime per-root and per-user ceilings. Reservations are retained even after failures/cancellation; they conservatively bound this pinned two-image/600-output-token request shape. Default ceilings are $1 global and $0.50 per user. Actual returned token usage is costed using standard input $0.40, cached input $0.10, output $1.60 per million tokens. This is a usage-based calculation, not an invoice. Failed requests without usage have unknown actual cost. Requalify prices and the reserve before changing model or request size; do not reset reservations to bypass the ceiling. No unbounded evaluation runner is enabled.

Official documentation consulted: [model snapshot and image support](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [image inputs](https://developers.openai.com/api/docs/guides/images-vision), [strict structured output](https://developers.openai.com/api/docs/guides/structured-outputs), [token prices](https://developers.openai.com/api/docs/pricing). `store: false` is not a promise of zero provider retention; provider data controls remain separate from local deletion.

## Verification and evidence

The committed runtime candidate and source tree, private preservation report, clean-checkout results and browser evidence are recorded in the private B3 handoff. No photos, credentials, copied collection data or browser evidence belong in Git.

Synthetic tests cover readable/ambiguous/unreadable/unsupported/failure states, content validation, metadata/orientation, refresh, capped retry, interrupted workers, cancellation during processing, exactly-once confirmation, intentional extra copies, provisional export, safe undo, cross-account image/job/action access, CSRF, revocation, expiry, provider request/schema validation and spend gates. The B2 browser harness also runs the B3 workflow when the fresh root has `B3_ISOLATED`; enable fixture mode before running it. Desktop and narrow Chromium are emulation only.

Real recognition evaluation: **0 photos, 0 API calls, $0 incurred by this work**. Correct matches, wrong matches, unresolved rate, real latency and real per-scan cost are **not measured**. Simulated results and mocked token arithmetic do not establish recognition accuracy. Missing setup: securely supplied `OPENAI_API_KEY`, switch the private configuration to `openai`, then evaluate a small consented representative set including readable supported, ambiguous, unreadable and unsupported cards. Record its composition, correct/wrong/unresolved outcomes, latency and returned usage cost before making a quality claim. The later held-out hosted-beta qualification remains open.
