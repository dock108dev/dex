# B5 phone walkthrough

Use the deployed HTTPS staging URL and **synthetic credentials only**. Run once on an actual iPhone in Safari and once on an actual Android phone in Chrome. Record device model, OS/browser version, UTC time, runtime commit and image digest. Desktop responsive mode does not count.

1. Sign in; refresh and reopen a page. Confirm the correct synthetic collection, no browser certificate warning, and a usable portrait layout. Sign out and verify Back/refresh does not restore private content.
2. Open Scan/Add. Try the camera chooser and take a photo of a synthetic test card; separately choose a library image. Check orientation and front/back selection. Cancel the chooser once: no job or copy should appear.
3. Try JPEG, PNG and WebP. Also try an actual HEIC/HEIF file from the iPhone library: the current server does **not** accept HEIC/HEIF. If Safari converts it to JPEG, record that observed conversion; otherwise expect the explicit supported-format error. Record what was actually uploaded, not just its filename. A failure must allow retry/manual entry. Try a too-large image and confirm a readable error.
4. Upload in clearly labeled simulation mode. Refresh while queued/reviewing; the same job must remain and inventory must not change. Confirm one copy once, refresh, and verify exactly one new physical copy. Edit the identity manually using Base Set or Neo metadata; unknown variants remain unknown.
5. Upload another photo, cancel the job, refresh, and verify no copy plus no accessible photo. Do not cancel the retained seed reservation to simulate a refund.
6. Create a provisional entry and catalog request, first with photos private and then explicitly shared. Use the second synthetic account to verify it cannot read the first account's inventory, direct photo URL or export. Only the owner-role reviewer can read explicitly shared request evidence.
7. Open a freshly operator-issued synthetic recovery link in the phone browser. It must land at `/access/`, then `/access/reset/`, with no token in subsequent request URLs. Set a new synthetic password, sign in, and verify reuse fails. Keep links/passwords out of screenshots and logs.
8. Export JSON and CSV from Settings. Confirm each file downloads/opens with only the signed-in account's records and exact purchase amounts. Rotate the phone, refresh and reopen the app; record camera permission, keyboard, scrolling or download failures verbatim.

Stop a failing flow, retain sanitized evidence, fix the concrete failure and repeat that flow. Do not infer owner acceptance or hosted reliability from a successful browser run.

| Actual device | Observation on September 28, 2026 | Result |
| --- | --- | --- |
| iOS Safari | No usable device session available. Local Apple device inventory is blocked by an unaccepted Xcode license; the task did not accept it. | Not run |
| Android Chrome | No configured device/ADB session available. | Not run |

The prior 390px Chromium observations remain browser emulation only. Recognition accuracy is a separate evaluation using suitable consented card images, not the geometric synthetic photos in the staging seed.
