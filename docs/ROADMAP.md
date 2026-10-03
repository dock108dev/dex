# Product roadmap

The supported scope is a single-user localhost collection and eBay hunting app.
Accounts, physical copies, binders, import/export, undo, catalog review, filtered
goals and private saved hunts are implemented. The original app and existing
stores remain supported; there is no automatic ownership cutover.

Prioritize the search → compare → reveal → seller review → save/reopen loop.
Bargain searches include owned cards; goal searches use frozen missing targets.
Keep conditional valuations, partial lot coverage and catalog-average benchmarks
explicit. Search results never add owned cards automatically.

## Remaining work

- Establish populated Production Browse evidence for comparisons, reveal, seller
  review and reopening. Provider access is installation-specific; see [hunts](hunts.md).
- Restore keyboard focus after the reveal dialog closes, including failed reveals.
- Review whether catalog browsing and physical-copy management need clearer navigation
  before changing those destinations.
- Evaluate real-card recognition accuracy and further photo integration when collection
  coverage expands. Existing manual, fixture, API and CLI modes remain available.
- Hosting, LAN access, managed startup, invited users and real-device qualification
  remain deferred. Preserve the optional staging implementation and its separate gates.

Preserve uncertainty, explicit ownership confirmation, intentional duplicates,
spending reservations, source provenance and conflict-aware undo.

[Current setup](local-development.md) · [Catalogs and goals](catalogs.md) ·
[Status](PM_STATUS.md) · [Historical evidence](history/README.md).
