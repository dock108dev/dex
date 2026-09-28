# Dex — PM status

Updated September 28, 2026. **Single-user localhost pre-alpha for Mike. Infrastructure work is deferred.**

The existing authenticated local app is the delivery target: [Overview](http://127.0.0.1:8011/overview/) and [Scan/Add](http://127.0.0.1:8011/scan/). Preserve its working login, collection, photos and prior environments. Endpoint availability was not rechecked during this documentation-only update.

B0 preservation, B1 account engineering, B2 collection/parity, B3 photo-entry workflow and B4 catalog expansion are implemented. Real recognition remains the next useful product task: the last handoff reports zero real API calls, no real recognition accuracy or latency measurements. Confirm current setup at execution time rather than assuming it is unchanged.

## Next action

**Lead engineer:** implement and evaluate `codex_cli` recognition using the saved Codex ChatGPT login. Retain the existing `openai` API-key provider for future deployment, plus manual/fixture modes. Use one shared matcher and confirmation flow; no automatic cross-provider fallback. The CLI is installed and was verified logged in during PM review; actual card recognition via CLI remains untested.

Keep API spending records intact. CLI runs consume subscription capacity; record attempts/latency/available usage separately without fabricated dollar costs. The model still processes images remotely. Use restricted noninteractive execution, validate results and handle timeout/cancel/login/limit failures.

**Mike:** provide suitable card photos if needed; no API key is required for the selected local CLI path. Preserve the existing login and collection. No infrastructure setup is required.

## Scope correction

Hosting, LAN HTTPS, cross-device testing, managed startup, reboot checks, external backup infrastructure and invited pilot are deferred. Existing operational code and evidence remain available for later use. Ordinary local backups, security/privacy checks and data preservation remain in scope.

The separate historical B1 actual-owner provisioning step is not required to use the working local login. Do not reset accounts or migrate data to satisfy that old gate. No authoritative cutover is performed by this decision.

Staging's missing prices/artwork/hunt projections must not be represented as deficiencies of the existing local app without checking that app. Preserve its established local experience and source/uncertainty labels. Recognition stays explicitly simulated until configured and evaluated.

[Authoritative roadmap](ROADMAP.md) · [Photo configuration](B3_PHOTO_ENTRY.md) · [Parity behavior](B2_PARITY.md). Earlier candidate evidence is retained in implementation documents and private handoffs. This update changes documentation only; no tests, service restart, credentials or collection changes are claimed.
