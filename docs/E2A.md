# E2a — explicit Original 151 goal versions

E2a is qualified for local synthetic engineering through runtime checks and the
[ordinary browser record](history/2026-10-04-E2A-BROWSER-QUALIFICATION.md).
Full E2, all-era coverage, owner acceptance and beta remain open. Earlier blocked
qualification sections below are historical. E3a implementation and its current
qualification limits are in [E3a closeout](E3A.md).

## Policy and version contract

`beta/broad_goals.py` owns `original-151-reviewed-v1`. Its fixed denominator is
canonical National Dex #001–151, using the retained canonical species names in
`config/catalog-imports/staging-ten/species.json`. Canonical Pokémon metadata can
qualify ex/V/GX, Dark, named/trainer-owned and regional printings. Trainers, Energy,
artwork cameos and unresolved species identities do not qualify. Evolution fills
only its own species. Duplicate physical copies or printings fill one species slot.
The legacy `dex_eligible` flag remains authoritative for existing vintage/filtered
goals; the broad policy does not silently change that flag or those goals.

Only current, explicitly reviewed collection publications qualify a new definition:
`catalog_heads` → published `catalog_imports` → Pokémon package → published set and
printing with the same version and approved canonical metadata. A provider record
or sealed-catalog row without a reviewed collection bridge does not qualify.
Booster membership is never an eligibility input. The 177 unresolved variant
membership rows retain their unknown distribution meaning. Reviewed provider
variants are recognized metadata identities, not claims of separate US physical
issues or confirmed booster availability.

Each retained goal row has its own ID and content digest in `version`. Its JSON
definition freezes the policy, 151 items, exact printing membership and catalog
references: set ID/name/version, review import ID and normalized package SHA-256.
`lineage` retains root ID, predecessor ID/digest and monotonic version number.
Successors are new rows; predecessors remain unchanged. One predecessor can have
one retained successor. Initial and successor confirmations are idempotent by the
existing account-scoped operation UUID. Explicit legacy Original 151 species-goal
conversion creates a broad successor; it preserves its original narrower policy.

The ordinary `/goals/` UI offers **Original 151 · any era · reviewed coverage v1**.
Creation preview shows policy, included catalog versions, every species, eligible
printing coverage, account-derived progress, missing species and unavailable
coverage. Update preview shows exact printing additions/removals, before/after
policy and account progress. Closing review cancels without goal writes. The
server re-plans under the existing transaction lock; changed collection generation,
predecessor revision/content, catalog membership/version or intervening successor
requires a fresh preview. Publishing catalogs only exposes an update-available
notice; it never enrolls new members into an older goal.

Progress reads only the session account's active copies. Both catalog unresolved
fields and provisional-copy unresolved fields prevent completion. It never uses
the original application's owned flags or the research missing-18 seed. An archived
printing can still satisfy the version that originally reviewed it, using its
retained resolved copy identity. Current published/selectable coverage is reported
separately from frozen printing membership. No-coverage species stay in the
151 denominator; the total missing count includes them. Missing with selectable
coverage and unavailable coverage are separate projections.

Retained versions cannot be deleted or overwritten through remove/edit/undo.
Undo of an older ordinary goal operation is also refused if a successor depends
on it. Other existing copy/binder/legacy-goal undo semantics remain conflict aware.
This deliberately retains version history instead of deleting a confirmed version;
review can be closed before confirmation or a new successor can be previewed.

## Actual included data

The fresh copied rehearsal recognizes **823 qualifying current printings** across
all 151 species: the ten retained vintage packages, reviewed Gym Heroes and the
reviewed Scarlet & Violet—151 bridge. The ten vintage packages use source version
`309aab7060b165925fee48573e730275dfbd737c`; Gym Heroes uses
`2026-09-28-9d19156dc3b1`; 151 uses `2026-10-04-151-v2`.
`evidence/e2a-20261004/first-goal.json` records every exact catalog reference,
printing member, account progress and digest. Counts describe this copied root,
not complete all-era coverage or the owner's collection. Its unresolved synthetic
copies give 0/151, with no inference of 133/151. The focused 151-only fixture has
346 qualifying Pokémon variants; its Trainer/Energy records do not enter goals.

The 151 package file SHA-256 remains
`250d0c61aea496d0854c831f62edb1030e1cd3acf91db59d239185528401a45f`;
its normalized service fingerprint is
`12ed07eb96fe8b3db79e33521028c12f19188ccb31eb0b17b97014644129ec34`.
The E1b manifest and all 34 files matched before work. Source data and its gaps were
not acquired, edited or reinterpreted by E2a.

## Persistence, import and hunts

No E2a schema migration is needed: existing JSON definitions, goal rows and operation
journals store the contract. Older B2 roots without catalog review tables remain
readable and can preview a 151 denominator with explicitly unavailable coverage.
Existing feature migrations are rehearsed twice on a disposable copied SQLite root.

`dex-collection-v2` exports now retain all goal versions and their policy/references.
Old exports still import. New imports validate exact 151 membership against retained
reviewed publication packages, reject forged species members/unsupported policies,
and require a complete internally consistent account-local lineage. All goal IDs,
root/predecessor IDs and predecessor digests are remapped to the importing account.
The source account's IDs never confer authority. Imports require compatible catalog
review journals; they do not publish arbitrary supplied catalogs or resolve missing
references implicitly. Account-local goal content digests change after remapping.

Goal-scoped search preparation explicitly captures the selected goal ID, digest,
kind and definition. Older saved hunts retain that snapshot and their query plan.
New searches use the selected version plus current resolved account ownership.
Archived metadata is recognized only inside a retained broad scope. Reopening and
filtering remain local, identities remain hidden until reveal, and the UI labels
current account ownership separately from frozen search scope. Goal selection shows
retained version numbers. No classic eBay defaults or provider activation changed.

## Reproduction and ordinary UI walkthrough

Run only against fresh synthetic/copy paths outside the checkout:

```sh
UV_CACHE_DIR=/private/tmp/dex-e2a-uv uv run --no-sync python -m pokemon_hunter.beta.synthetic --output NEW_SEED
UV_CACHE_DIR=/private/tmp/dex-e2a-uv uv run --no-sync python scripts/rehearse_e2a.py --seed NEW_SEED --root NEW_COPIED_ROOT --output NEW_EVIDENCE
```

The script creates an older saved hunt, backs up the synthetic SQLite database,
checks repeated migrations, publishes only retained local packages, creates and
updates a broad goal, closes a preview without writes, imports both versions into
the second synthetic account, and reopens older/broad saved hunts with provider
calls prohibited. It compares pre-existing rows and reservation-bearing scan jobs.
`preservation.json` pins baseline table hashes and input packages. Earlier failed
report serialization output is retained; the final rehearsal used a fresh root.

For the remaining browser gate, start only the disposable copied root from an
ordinary terminal that permits a loopback listener (no owner-root substitution):

```sh
uv run --no-sync python -c 'from pathlib import Path; from pokemon_hunter.beta.cli import setup; setup(Path("/private/tmp/dex-e2a-20261005-copied-qualified")); import uvicorn; from django.core.asgi import get_asgi_application; uvicorn.run(get_asgi_application(), host="127.0.0.1", port=8011, access_log=False, proxy_headers=False, log_level="warning")'
```

Use the generated `admin` credentials in that root's private `credentials.json`;
never copy credentials into evidence or prompts. Start a fresh browser session at
`http://127.0.0.1:8011/goals/`. Create **Browser Original 151**, select the broad
choice, inspect policy/catalogs/151 checklist/current progress and missing coverage,
and confirm once. Open progress, filter missing species and unavailable coverage.
Preview its successor, inspect the additions/removals and progress/policy comparison,
then close review. Confirm the goal list is unchanged. Preview again, confirm the
fresh successor and reopen both retained versions. Check their version numbers,
references and frozen lists. On each version's Missing singles page choose samples
only; reopen Saved finds, verify captured version and hide/reveal/filter behavior.
Never click Search eBay. Capture creation, progress, canceled review, successor and
both reopened versions. Record browser errors and every actual assertion. These
steps remain **pending** until renewed explicit permission and execution.

## Original implementation closeout and blocked qualification attempt

E2a runtime qualification now passes: locked synchronization, all three process
cleanup cases and the full suite (458 passed, one existing warning), plus compilation,
JavaScript syntax, lint and formatting. Fresh copied-state preservation and zero-call
frozen-hunt service assertions pass. E2a remains partial: renewed explicit browser
permission was requested and is pending; no server, navigation, UI captures or owner
acceptance occurred. [Qualification record](history/2026-10-04-E2A-QUALIFICATION.md)
retains commands, runtime, exact hashes and preservation evidence. Full E2 and beta
remain open.

One next bounded action is **finish the E2a synthetic browser qualification** after
renewed explicit permission. Verify the new final manifest, then run the retained
create/progress/cancel/successor/reopen and sample-hunt walkthrough. Stop at the first
unmet gate; bind any repair to fresh tests/hashes and a fresh browser boundary.
No acquisition, pack-shopping implementation, live providers, owner-root writes or
hosting is authorized by this slice.

The original implementation manifest and validation remain historical and unchanged.
The intentional Desktop handoff overlay was verified, then the handoff was updated
for this partial qualification. The new final manifest is retained under
`evidence/e2a-qualification-20261004/validation-final/`.

## Current next step

The earlier runtime/browser blockers are resolved for local synthetic qualification.
Proceed to bounded E3a pack discovery using retained reviewed data; keep unavailable
contents/stock and remaining data gates explicit. See the browser qualification
record and current Desktop handoff. The saved Desktop replacement was applied before
runtime qualification; the Desktop handoff is now updated to E3a.
