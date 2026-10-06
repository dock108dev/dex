# E2d — collection-based Original 151

October 5, 2026. Implemented and qualified on disposable synthetic SQLite state with the supplied photo-reconciled CSV. Owner application remains a subsequent reviewed update. This closes the narrow E2d component; the broader M1 Pokédex/251 workflow remains open.

Entry HEAD `16766b5c160c0bac370c1177387662646bf51b42`, handoff manifest SHA-256 `92405da6644bf881d641ef9f9c1e4425fd8675c508eb325badb5a0099fe657b1`: all 967 listed files matched before editing. The current user assignment explicitly selects E2d despite the retained prompt's superseded notice. Inherited changes, evidence and M1 requirements are preserved.

## Behavior

Goals offers **Original 151 · collection species ownership**, separately from **Original 151 · any era · reviewed coverage v1**. Explicitly select an account-local complete 251 collection source and preview before confirming. The new policy is `original-151-collection-v1`, stored as `original151_collection`. It freezes canonical species #001–151, source account/ID/SHA-256/revision, reviewed catalog references, printing memberships and version lineage. Full-source validation requires all 251 canonical CSV rows, consistent Owned/Missing declarations and valid supplied card marks. Duplicate cards fill one species slot; Dark, named and EX cards count for their canonical species.

Authoritative input: `outputs/my-have-dex-001-251-photo-reconciled.csv`, SHA-256 `511dec82f4434e1e90ae27ec634e85e546f7559d43cc61d4cabec310d4ccc1b2`. Preview and persisted progress are **137 owned / 151; 14 missing**:

Venusaur, Pidgeotto, Pidgeot, Alakazam, Gengar, Hypno, Chansey, Kangaskhan, Mr. Mime, Scyther, Gyarados, Lapras, Jolteon and Moltres.

Declared ownership remains valid with zero reviewed printing coverage. `reviewed_printing_species`, qualifying printing counts and uncovered species are separate measures. Packs derives missingness from the selected frozen species source and retains its reviewed printing/product joins. Source presence creates no card printing, physical copy, edition, finish, quantity, booster membership, product contents, stock or purchase claim. Classic goal-scoped eBay species scoring uses declaration ownership without labeling unowned card printings as owned. Existing reviewed-copy goals continue to use resolved active copies.

The original source bytes retain all names, numbers, rarity text and notes, including Clefable — Plasma Storm #98, Articuno-EX #25, Dark Vaporeon #45 and Dark Flareon #35. Special markers remain unresolved physical-printing evidence. Supplied missing-90 pack claims are not used as distribution evidence.

## Updates, portability and rollback

A new declaration does not change an existing goal. Select a source on the goal card, preview a successor, review source hashes and added/removed owned species, then confirm. The predecessor and its frozen version remain intact. Only one successor per predecessor is permitted. Reviewed catalog changes likewise require a new version. Canceling a preview applies nothing.

Saving Packs research freezes ownership, source/version, scope, offer filters, reviewed identities and original observations. Reopening after an app restart retains that snapshot and dates. Successor creation never rewrites saved predecessor research. Stock and official product contents remain separately qualified.

JSON exports containing collection goals add `collection_sources` with original source bytes and provenance. Exports without these goals retain their previous shape. Imports recompute hashes, canonical species and reviewed memberships, require complete source references and lineage, verify frozen digests, and remap declaration/goal IDs and predecessor versions into the importing account. Reconciliation is recomputed for that account; supplied printing-resolution claims are not trusted. Confirmation rechecks the preview and account generation in one transaction. Retrying an operation/import is idempotent; imports cannot access another account's local source or saved research.

There is no new table migration. The existing explicitly enabled ownership-declaration feature must be available. Unreferenced declaration operations can be undone. Retained goals and referenced sources cannot be erased by undo; corrections use successors. Injected import failure after source insertion rolls back the whole transaction. A full SQLite backup restore is also rehearsed on a separate disposable database, preserving the earlier goal/source boundary. No automatic rollback erases predecessor versions or saved research.

## Qualification and reproduction

See [dated validation](history/2026-10-05-E2D-VALIDATION.md), [repository checks](../evidence/e2d-20261005/repository-checks.json), [full suite](../evidence/e2d-20261005/full-suite.txt), and [browser preservation audit](../evidence/e2d-20261005/browser/verification.json). Screenshots under `evidence/e2d-20261005/browser/` cover source/missing preview, persisted goal, whole-goal Packs, filtered save, server restart, successor preview, retained versions and final reopen. Final candidate identity is `evidence/e2d-20261005/candidate.json` with adjacent `candidate.sha256`.

Use fresh paths outside the checkout for private synthetic state; do not substitute the owner root:

```sh
uv sync --locked --extra dev --offline
uv run --no-sync python scripts/rehearse_e2d.py --root /private/tmp/dex-e2d-NEW-state --output evidence/e2d-NEW-browser
uv run --no-sync python scripts/serve_e4a.py --root /private/tmp/dex-e2d-NEW-state --output evidence/e2d-NEW-browser --port 8025
```

Choose an unused loopback port. The disposable-only server retains exact Host/Origin, loopback and forwarded-header protections for that port and blocks provider calls. Use generated `admin` credentials in the private synthetic root's `credentials.json`. In the ordinary browser, open `/login/`, sign in, go to Goals, name the new collection goal, select its collection policy/source, preview 137/14 and confirm. Open Packs; select Scyther, choose an offer filter, apply and save. Stop/restart only this disposable server with the same command, then reopen the saved entry. Preview/confirm a successor on the goal card and reopen predecessor research.

```sh
uv run --no-sync python scripts/rehearse_e2d.py --root /private/tmp/dex-e2d-NEW-state --output evidence/e2d-NEW-browser --verify
uv run --no-sync pytest -q tests/test_collection_goals.py tests/test_broad_goals.py tests/test_ownership_declarations.py tests/test_pack_research.py tests/test_packs.py
uv run --no-sync pytest -q
```

Tests include a synthetic changed source declaring Venusaur owned: successor becomes 138/13 while its predecessor and saved research remain 137/14. This is a test fixture, not an owner collection update.

## Remaining gates and next action

No acquisition/provider calls, purchases, credential changes, hosting or owner-installation writes. Existing source budgets remain closed. PostgreSQL execution, owner acceptance and full beta acceptance are not qualified. All-era catalog/product coverage, official contents, current eligible offers and broader M1 collection maintenance/251 UX remain open.

One bounded next action: verify this final manifest, back up the existing owner installation, review the authoritative source and explicitly create its new collection-based Original 151 goal with a 137/14 preview, preserving all prior versions and saved research. Apply only under the subsequent reviewed owner-update authorization.
