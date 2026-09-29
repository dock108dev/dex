# B5 closeout — Mac-hosted private staging

> **DEFERRED — optional future reference, not active next steps.** Mike’s September 28 direction makes the existing localhost app the sole current target. All setup/checklist requirements below are inactive for current local use, including hosting/LAN HTTPS, device tests, managed startup/reboot and external backup infrastructure. Preserve prior evidence; do not execute this runbook unless that scope is reopened. The [current roadmap](2026-09-28-ROADMAP.md) takes precedence.


**Current decision: use Mike's Mac, with phones on the same trusted home Wi-Fi. Render, GHCR publishing and paid hosting are not required. B5 remains OPEN until the observations below are recorded.** This replaces the Render account/provisioning next step. It does not turn earlier emulation into actual phone evidence.

The existing Django web process, independent worker and PostgreSQL 17 run on the Mac. Use the isolated synthetic staging database, not Mike's collection or historical private evidence. Keep the original review app on 8011 and previous loopback staging on 8443 intact. No invitations, public signup, router port forwarding, public tunnel or authoritative collection cutover is part of this closeout. Away-from-home access can be a separate later requirement; it is not necessary for this home-network scope.

## Exact candidate and existing evidence

Runtime: `0f17cc9ff337ee1ce90cdb32875afd7de6d03e38`, documented at `9af1848`. Retained Linux AMD64 image: `sha256:46facd36fc6bb15603960722bba10e015bc4189a73ef30a0208be051a6a52c8b`. [Release manifest](../../deploy/release.json) identifies that artifact; its intended GHCR destination is historical, not a requirement to run the retained image locally. It already ran on this Mac during package verification. No new runtime/image is created by this documentation change. A later native ARM64 build would be a distinct image and must be recorded as such.

Private evidence remains at `/Users/michaelfuscoletti/dex-private/b5-followup-20260928/`: 198 passing tests in working/clean checkouts, Python 3.12/3.14 CI, synthetic PostgreSQL migration/isolation, final-image backup/empty-target restore, preservation of a post-backup write and a $0.05 reservation, and local Chromium recovery. Keep each result tied to its actual candidate and environment. Those PostgreSQL results are valid Mac observations; they were never cloud-provider observations. Do not rerun the full suite or restore drill merely because the selected hosting provider changed. Repeat only checks affected by changes, or checks whose existing evidence does not cover the final deployment.

## Work needed to close B5

| Work | Who | Evidence required / current state |
| --- | --- | --- |
| Reach staging from a phone using trusted HTTPS | Engineer sets up a dedicated home-network HTTPS endpoint; Mike makes the phones available | Stable Mac hostname/address, certificate trusted on both actual phones without warning bypass, exact Host/Origin and proxy checks. Backend and DB remain private; expose only the intended TLS endpoint to the home network. **Not observed yet.** |
| Keep the app and worker running reliably | Engineer | Managed startup/restart for web, worker and PG storage; observe process restart plus Mac restart/login recovery on the final configuration, retained writes/jobs/reservations and readiness. Record sleep/offline behavior. Mac must be awake and connected for access. Schedule any Mac reboot with Mike; do not interrupt unrelated applications. **Final configuration not observed yet.** |
| Exercise real access and core flows | Engineer with synthetic accounts | HTTPS login/recovery, secure sessions, cross-account inventory/export/photo denial, private/shared/revoked photo consent, manual add/edit/duplicate/undo/export, frozen goals, catalog publish/rollback and same-copy request resolution, fixture scan/refresh/cancel, worker restart and scanning disable. Reuse unchanged component evidence; verify access through the final endpoint. **Final endpoint not observed yet.** |
| Complete recoverability on the chosen Mac setup | Engineer; Mike identifies an available backup destination | Existing PG17 exact-image restore already passed. Configure and observe recurring backup/expiry; keep a protected copy on a separate physical device or existing encrypted storage so losing the Mac does not lose every backup. Restore only to an empty separate target. Repeat restore if storage/runtime/schema changes affect the earlier evidence. Preserve newer source writes and all reservations. **Scheduling and independent backup copy not observed yet.** |
| Run actual phone walkthroughs | Mike uses iOS Safari and Android Chrome; engineer records observations and fixes failures | [Short walkthrough](2026-09-28-B5_PHONE_CHECKS.md): camera/library, formats including HEIC handling, confirm/cancel, refresh, recovery/login, export. Record model/OS/browser, endpoint, candidate and actual outcomes. Xcode and ADB are not required for a manual walkthrough. **Both actual-device results missing.** |
| Record the closeout | Engineer | Exact runtime/image + non-secret deployment configuration identity, URL, observation/evidence table, start/stop/recovery instructions and remaining limitations. Mark only obtained results PASS. **Pending the above.** |

The existing loopback rehearsal proxy and browser certificate exception are not the phone-facing HTTPS solution. Use the staging `proxy` profile (`DEX_INGRESS=proxy`) and a verified narrow proxy-peer allowlist; do not spoof Render environment variables or relax Host/Origin/TLS checks. The HTTPS proxy must replace incoming forwarded headers, and direct access to the backend must remain blocked. Configure `DEX_PUBLIC_ORIGIN` to the exact phone-facing HTTPS origin. Reuse the isolated target's existing secrets; the separately generated unused application secret is not a reason to rotate a running environment. Never reset the synthetic database or spending rows to simplify setup.

## Mike's inputs

1. An iPhone and an Android phone available on the same home Wi-Fi for the walkthrough. If either is unavailable, record that platform as unverified; do not mark the required phone coverage complete.
2. An existing external drive or encrypted backup destination for one independent backup copy.
3. A convenient time for the eventual Mac restart/recovery check. Ordinary setup does not require another stage approval.

Engineer-owned next action: inspect the existing isolated services and home-network configuration, configure the dedicated trusted HTTPS endpoint, and provide its usable URL plus the device trust/setup steps. No Render login or registry token is needed. Any required device certificate-trust action is done deliberately on the test devices; do not bypass certificate warnings.

## Recognition and retained limitations

Real recognition is a separate B3 qualification dependency, not a reason to stop the Mac operational checks. If a securely configured key and suitable consented labeled images become available, run the existing bounded evaluation within the unchanged $1 global / $0.50 account ceilings and $0.05 reservations. Otherwise keep manual/fixture operation explicitly simulated: zero real calls/$0 real spend; correct/wrong/unresolved counts, real accuracy and latency remain unmeasured. Closing Mac operational B5 must never be described as real-recognition qualification or invited-beta readiness; B3 and the broader pilot acceptance requirements remain open.

Supported staging coverage remains 991 Pokémon entries plus two synthetic variants and 251 named species. Prices, external artwork and guide/hunt parity remain unavailable. No full local-feature-parity claim. Actual B1 owner provisioning remains independent; B6 does not start automatically.

No new hosting subscription is needed for this Mac/home-network scope. Existing electricity, storage and internet remain the user's resources; any newly required backup hardware or paid service must be identified before purchase. The inactive [Render package](2026-09-28-B5_RENDER_REFERENCE.md) remains reference material only.
