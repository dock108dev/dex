# Product roadmap

The current scope is a single-user localhost collection app. Accounts, physical
copies, goals, imports/exports, photo review, catalog requests and spoiler-safe
sample/saved hunts are implemented. The original app and existing stores remain
supported; there is no automatic data cutover.

The next product question is real-card recognition quality. CLI and API adapters
exist, with explicit provider selection and shared matching/confirmation behavior.
Evaluate a small consented, independently labeled photo set before claiming
accuracy. Synthetic transport checks do not answer that question.

Hosting, LAN access, managed startup, real-device qualification and invited-user
rollout are deferred. Retain the optional staging implementation without treating
its unfinished deployment requirements as blockers for local use.

Preserve uncertainty, confirmation before ownership changes, intentional duplicates,
spending reservations, source provenance and safe undo. The next engineering work
should address demonstrated local defects or evidence from recognition evaluation.
Navigation overlap remains a product-design follow-up.

[Current setup](local-development.md) · [Photo entry](photo-entry.md) ·
[Historical decisions and candidate evidence](history/README.md).
