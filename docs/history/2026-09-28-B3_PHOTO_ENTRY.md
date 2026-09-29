# B3 photo entry — local pre-alpha

## Codex CLI local delivery — September 28, 2026

`codex_cli` is implemented and selected for Mike's existing localhost app. The installed **Codex CLI 0.144.6** reports saved ChatGPT login and supports `exec --image`, `--output-schema`, `--ignore-user-config`, `--ignore-rules` and `--ephemeral`. The adapter pins **gpt-5.6-sol**, which the installed CLI's model catalog lists with image input. Authentication is managed by Codex; Dex never reads or copies its tokens. The subprocess receives an environment allowlist without API keys or app secrets and forces ChatGPT login. Images are sent to OpenAI; subscription limits apply. Remaining subscription capacity is **unavailable** in the observed exec output, not unlimited or free.

Each request gets a 0700 temporary directory and 0600 normalized image/schema/output files. User configuration/rules and project instructions are disabled; hooks, plugins, apps/connectors, skills instructions, memories, shell/code execution, browsers and agent delegation are disabled. An explicit permissions profile denies model filesystem access outside the temporary directory, permits only reads within it, and disables model network access. The CLI transport can still authenticate and send attached images to OpenAI. No inventory or collection data is supplied. Non-message action events are rejected. Temporary payloads and captured diagnostics are removed in `finally`; diagnostics are never copied into user messages or logs.

One CLI request per root is enforced by transactional job claims and a process lock, with a 75-second deadline, bounded output, zero configured request/stream retries and at most two user-requested attempts per job. Cancellation, account revocation, disabling scans and graceful worker/app shutdown stop the subprocess group (TERM then KILL) and clean temporary images. Hard process/OS termination cannot run Python cleanup; the existing 120-second interrupted-job rule still prevents automatic retry. Missing/incompatible CLI, expired login, usage limits, malformed output and timeout lead to clear manual-entry alternatives, never API fallback.

Both providers validate the same `Clues` schema and call the unchanged matcher, review, exactly-once confirmation, intentional duplicate and safe undo paths. CLI jobs reserve no API dollars and have no API cost estimate. Existing API reservations/ceilings remain unchanged. Private `PRIVATE_ROOT/codex-usage.jsonl` records each CLI attempt (including failures/cancellation), whether a subprocess started, outcome, model, latency, reported token counts and unavailable remaining capacity. It contains no photos, raw model text or credentials. Back it up with the private root. The scan job exposes attempts/last latency and successful returned usage; the sidecar retains every attempt independently of later retries.

### Current verification and real-photo gap

Two retained live synthetic controls completed on the final adapter: blank image **3.536 s**, instruction-bearing non-card image **3.660 s**. Both returned `unreadable` and all identity fields null; neither made tool/action calls. Reported input/output tokens were 7,658/46 and 7,662/46 (6,144 cached input on the second). These verify image transport, structured output and restraint only. An earlier development blank control also succeeded in 5.104 s; startup compatibility failures led to the corrected provider configuration, permissions syntax and image/prompt argument separation. No API-provider requests were made.

**Real-card evaluation: 0 photos; 0 correct, 0 wrong, 0 unresolved. Accuracy is not measured.** No labeled card photos were supplied and the existing local scan store has zero photos. Remaining input: one to six consented front photos with independently verified card name, collector number and set, including a clear supported card and difficult/unsupported examples. Do not use manual corrections as recognition successes.

For a bounded pre-correction evaluation, create a private manifest using the example in `scripts/evaluate_codex_photos.py`, then run:

```sh
uv run python scripts/evaluate_codex_photos.py --manifest /absolute/private/labels.json --output /absolute/private/new-evaluation
```

The output directory must not exist. This runs at most six CLI requests, writes private clues/outcomes/latencies/token usage, and makes no collection changes or API charges. It scores complete visible name/number/set identity against preassigned labels; missing identity is unresolved, conflicting complete identity is wrong. Catalog support remains a separate matcher result.

Private preservation backup and live-control evidence: `/Users/michaelfuscoletti/dex-private/codex-recognition-20260928/`. **216 tests passed** (one existing Starlette TestClient deprecation warning); lint, formatting, JavaScript syntax and diff whitespace checks passed. The final error-message adjustment also passed all 18 CLI-specific tests. The restarted localhost Scan/Add endpoint redirects unauthenticated requests to the existing login. A before/after digest comparison found every database table and all existing credential/marker/evidence files unchanged; only the requested scan mode changed, with API ceilings preserved. No account, collection or photo records were added for these controls.

Current checks cover subprocess privacy/configuration, validation, bounded output, missing/login/limit failures, process-group cancellation/timeout, concurrency, provider switching, separate usage, unchanged API budget tests, and confirmation/undo. Historical runtime evidence below remains historical.


September 28, 2026. B3 engineering is implemented in the authenticated Django app. Actual owner provisioning, hosted operation and real-device acceptance remain separate. No live collection cutover, deployment, purchase or marketplace search is included.

## Use

Open `/scan/` from Scan/Add. Choose one front and optionally one back or close-up from the camera/library, upload, review candidates, select a supported catalog entry or retain an unidentified card, enter corrections/notes, check the review acknowledgement and confirm one physical copy. Existing copies produce a warning; intentional duplicates use a new photo entry. Refresh reopens the durable job. Manual catalog entry remains available from Collection.

Selecting **fixture mode** prominently labels results SIMULATED. Its outcomes are deterministic catalog examples, not identification of the uploaded photo. Choose readable, ambiguous, unreadable, unsupported or failed to exercise the flow. Missing credentials do not prevent private photo storage, manual matching, provisional additions or undo.

Copy creation uses the existing revisioned collection journal, physical-copy store and derived views. The job ID is the stable confirmation identity. Retrying confirmation returns the same operation; an undone operation cannot be reapplied. Undo checks after-images and refuses to overwrite later edits. Cancellation and worker completion never create copies. Scan provenance links retained photos from Collection; edition/language/finish/variant uncertainty survives confirmation. Provisional records have no printing ID and cannot satisfy exact-printing goals or receive verified printing values. Corrections and selected identity are private evidence, never automatic catalog changes.

## Private storage and jobs

Private normalized JPEG bytes are stored in the existing owner-only SQLite database, scoped to account and job. There is no public media directory or arbitrary URL ingestion. Every image/job/action rechecks active account mapping; worker execution derives identity from its persisted job and checks it again after recognition. Response caching is disabled. Invalid content, animation, oversized files, tiny dimensions and decompression bombs are rejected. JPEG/PNG/WebP input is limited to 8 MB per image, 200px minimum, 24 megapixels maximum and 10,000px maximum dimension; images are orientation-corrected, resized to at most 1600px and re-encoded without metadata. HEIC is not supported; use a compatible camera/browser export.

A background worker started by `serve` claims database jobs outside page requests. An independent `scan-worker` command is also available; transactional claims prevent duplicate processing. States: queued, processing, needs-confirmation, needs-better-photo, unsupported, failed, cancelled, confirmed. Worker interruption after 120 seconds becomes failed, requiring explicit retry. Late results compare their claim timestamp and cannot overwrite cancelled or newer attempts. At most two provider attempts per job, with no automatic retry of possibly billed calls. Upload quota is 20 entries per user per rolling 24 hours.

Unconfirmed uploads expire after seven days. Confirmation retains them with the copy. Cancellation/undo deletes image bytes; removal blocks serving immediately and worker cleanup removes bytes. Delete retained photos is available independently of copy removal. Revoked accounts lose image access immediately and worker cleanup removes bytes. Job metadata and operation provenance remain for audit. Existing private backups may retain old bytes until an operator deletes those backups; hosted backup expiry/account erasure remains B5 work. No image sharing or training consent is inferred.

## Recognition configuration

Enable B3 in an existing **isolated B2 root** using `uv run python -m pokemon_hunter.beta.cli --root PRIVATE_ROOT enable-scans`, then restart its server. This adds tables and a marker without resetting identities, passwords, inventory or existing operations. Back up the private database before upgrading. Do not run this against the original collection.

`PRIVATE_ROOT/scan-config.json` (owner-only) selects the provider. For the existing local app, that file is `/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local/scan-config.json`:

```json
{"enabled": true, "mode": "codex_cli", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5}
```

Change **only `mode`**, preserving the existing ceilings and every spending record:

- `codex_cli`: existing saved Codex ChatGPT login; `codex` must be on the server's PATH. If needed, sign in through `codex login` outside Dex. No API key is required.
- `openai`: deliberate future API-key provider. Supply `OPENAI_API_KEY` securely to the server/worker environment and restart it; never put keys in configuration, source or logs.
- `manual`: retain photos and choose catalog identity yourself.
- `fixture`: explicitly simulated test results.

Mode changes are read for new jobs without restart. A queued job from a different mode fails with a provider-changed message; it is never rerouted. An already running request keeps its original provider. `enabled:false` stops new work and cancels an in-flight CLI request; it cannot recall an API request already sent. Manual collection entry and review remain available. New roots still default to manual; do not reinitialize the working local root to change modes.

Model snapshot: `gpt-4.1-mini-2025-04-14`; prompt, schema and matcher version: `dex-photo-v1`. Server-side Responses API, inline image bytes, strict JSON schema, no tools, `store: false`, maximum 600 output tokens, 5-second connect and 35-second network inactivity timeout. Model evidence is validated again locally, then matched by name and every supplied number/set/language clue against the existing catalog. Conflicting clues never silently fall back to an exact match. Candidates remain user-reviewed; the model cannot publish catalog rows or mutate ownership. Edition/finish/variant/language clues are displayed but never automatically asserted on a copy.

Each `openai` API request reserves $0.05 before transmission, transactionally across workers, against lifetime per-root and per-user ceilings. Reservations are retained even after failures/cancellation; they conservatively bound this pinned two-image/600-output-token request shape. Default ceilings are $1 global and $0.50 per user. Actual returned token usage is costed using standard input $0.40, cached input $0.10, output $1.60 per million tokens. This is a usage-based calculation, not an invoice. Failed requests without usage have unknown actual cost. Requalify prices and the reserve before changing model or request size; do not reset reservations to bypass the ceiling. No unbounded evaluation runner is enabled.

Official documentation consulted: [model snapshot and image support](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [image inputs](https://developers.openai.com/api/docs/guides/images-vision), [strict structured output](https://developers.openai.com/api/docs/guides/structured-outputs), [token prices](https://developers.openai.com/api/docs/pricing). `store: false` is not a promise of zero provider retention; provider data controls remain separate from local deletion.

## Verification and evidence

The committed runtime candidate and source tree, private preservation report, clean-checkout results and browser evidence are recorded in the private B3 handoff. No photos, credentials, copied collection data or browser evidence belong in Git.

Synthetic tests cover readable/ambiguous/unreadable/unsupported/failure states, content validation, metadata/orientation, refresh, capped retry, interrupted workers, cancellation during processing, exactly-once confirmation, intentional extra copies, provisional export, safe undo, cross-account image/job/action access, CSRF, revocation, expiry, provider request/schema validation and spend gates. The B2 browser harness also runs the B3 workflow when the fresh root has `B3_ISOLATED`; enable fixture mode before running it. Desktop and narrow Chromium are emulation only.

The original API-only delivery made zero API calls; its historical validation does not establish recognition accuracy. Current CLI controls and the remaining real-photo input are documented above.

### Tested runtime candidate

Runtime commit `a456ab7fcc3db5c22860c8d90d217196309b1ce2`, tree `74e7bf4aafd96a83c4aa52395ed60c5a54583b89`: **173 tests passed** in both working and clean checkouts; lint, formatting and JavaScript syntax checks passed. The clean-checkout browser run passed B2 parity plus B3 flows in independent 1280px and 390px Chromium contexts. Desktop/narrow screenshots were inspected; the discovered low-contrast scan buttons were repaired before this candidate. One existing Starlette TestClient deprecation warning remains. No real iOS/Android observation is claimed.

Private evidence: `/Users/michaelfuscoletti/dex-private/b3-photo-20260928/`, including `clean-regression.txt`, `clean-browser/browser-report.json`, desktop/narrow scan reports and screenshots, `preservation.json`, `review-upgrade.json`, and `handoff.json`. Original source data and restored-app checks passed. Every pre-existing review database table and credential/config file matched its pre-upgrade hash; only B3 tables, its enable marker and private scan configuration were added. This documentation closeout does not change the tested runtime.
