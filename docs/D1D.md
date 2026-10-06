# D1d — English Detective Pikachu retained acquisition and import rehearsal


## Current status after E1c — October 5, 2026

**The full 18-card publication gate is repaired and locally synthetic qualified.**
[E1c](E1C.md) supports all canonical identities through the retained 1,025-species
registry and preserves unknown edition/finish. Fresh synthetic preview, reviewed
publication, idempotency/conflicts, rollback/restoration and the ordinary-browser
13-printing Original 151 successor passed. Existing goals and protected state
remain intact; Packs confirmed coverage remains zero. Acquisition calls: zero;
D1d's 19-attempt budget remains closed. [New reconciliation](../evidence/e1c-20261005/reconciliation/per-set.json)
records 18 demonstrated synthetic imports, separate from source normalization and
owner deployment. All-era coverage and full beta/owner acceptance remain open.

The concrete remaining blocker is official Detective Pikachu booster/promo/deck
applicability for all 18 relationships. The original stopped gate, rejected bridge,
normalization and reconciliation below are historical and retained unchanged.

## Historical D1d acquisition and stopped gate

October 5, 2026 (America/New_York). **Acquisition and offline metadata normalization
complete; reviewed import rehearsal blocked before publication. D1d is partial.**
All 18 numbered identities are retained and validated. No partial subset was imported.
Full all-era coverage and full beta/owner acceptance remain open.

## Baseline and bounded acquisition

HEAD `16766b5c160c0bac370c1177387662646bf51b42` matched. D1c candidate
`evidence/d1c-20261005/validation-final/candidate.json` SHA-256
`4bcfdc15e623939ebd9f485fec3f9fc5a31e5a1bcef93e26198d3f779c7b9fee`
matched, and **all 770 listed files matched before work**. Inherited source changes,
D1c's original baseline/input lock and earlier budgets/evidence are preserved.
No applicable repository/ancestor AGENTS.md was present. Read D1C.md, beta contract,
Desktop tracker, catalog guide, D1/E1 and D1/E1b source/rights records, normalizers,
sealed/collection import and bridge services, and broad-goal workflow before work.

The user's D1d authorization permitted one provider, one English set, at most
19 attempts, zero retries. [Attempt ledger](../evidence/d1d-20261005/attempt-ledger.json)
records durable reservations before invocation, exact URLs, UTC invocation/completion
times, outcomes, transport exits, retained response locations and SHA-256 hashes.
The one-shot acquisition script refuses any existing ledger, including an interrupted
budget. Earlier acquisition budgets were not reopened.

- One GET of `https://api.tcgdex.net/v2/en/sets/det1`.
- Exactly 18 sequential GETs using only the explicit IDs returned in that response.
- All 19 returned HTTP 200 and usable JSON; zero retries, redirects or failures.
- Acquisition: `2026-10-05T19:57:59.300716+00:00` to
  `2026-10-05T19:58:01.602308+00:00`, elapsed 2.302 seconds.
- 31,011 body bytes, within the 10 MiB ceiling; 15-second per-attempt and
  five-minute acquisition deadlines applied. **Budget closed, 19/19 consumed.**

Raw bodies, response headers and separate transport output remain private under
`/Users/michaelfuscoletti/dex-private/d1d-20261005/source-evidence`.
Transport diagnostics are not response evidence. No denial or transport failure
occurred; no tool output is substituted for source bytes. [Input lock](../evidence/d1d-20261005/inputs.json)
pins every retained file, the registry package/license and D1c reconciliation inputs.
No list/search/discovery endpoints, other set, official/retailer reads, credentials,
provider activation, live offers, purchases, bids, hosting or deployment occurred.
The prohibited owner review root was never accessed or operated.

## Supported metadata and uncertainties

[Validated metadata package](../config/sealed/2026-10-05-det1/package.json) uses
`dex-sealed-v1`; [normalization rows](../config/sealed/2026-10-05-det1/normalization.json)
retain exact provider IDs, numbers, categories, canonical species, source hashes
and provider variant descriptions. Explicit mappings retain `tcgdex` / `en` /
`det1`, expansion `tcgdex:en:det1` and distinct provider-described printing IDs.
The returned ID set equals the normalized numbered ID set exactly; duplicate IDs,
number drift, category/species conflicts and unknown canonical registry IDs fail.

| Measure | Result |
|---|---:|
| Expected / retained / normalized numbered identities | 18 / 18 / 18 |
| Pokémon / Trainer / Energy | 18 / 0 / 0 |
| Distinct canonical species | 18 |
| Qualifying Original 151 numbered printings / species | 13 / 13 |
| Provider-described variant records / normalization cap | 18 / 72 |
| Verified physical variant count | Unknown |
| Verified booster / promo / deck relationships | 0 / 0 / 0; all 18 unknown |
| D1d collection imports / reviewed publications | 0 / 0 |

Canonical mappings come from provider `dexId` joined to the retained 1,025-species
registry. Names/cameos are not mapping authority. Detective Pikachu `det1-10`
resolves to canonical Pikachu #025 despite its named label. Original 151 overlap:
Bulbasaur, Charmander, Charizard, Arcanine, Psyduck, Magikarp, Pikachu, Mr. Mime,
Mewtwo, Machamp, Jigglypuff, Lickitung and Ditto. Other mapped species are Ludicolo
#272, Morelull #755, Greninja #658, Snubbull #209 and Slaking #289.
The retained missing-18 research seed overlaps only Mr. Mime; this is catalog
research, not current account missingness or an ownership/completion change.

Every detail describes `normal`, `standard`, `variantId: generated`, with normal
true and holo/reverse/firstEdition/wPromo false. These are **provider descriptions**,
not verified physical finish/edition/distribution. Normalized verified finish is
null; verified edition/distribution and expected physical variant count stay null.
Printing variant identity is `provider-normal-generated`, explicitly scoped to
this provider description. No holo, nonfoil, unlimited physical issue or US
release claim is inferred. All 18 membership records are `unknown`; there is no
new official source in this budget. Products, packs, guaranteed cards and offers
are empty. There are no stock, purchasability or pull-probability claims.

The retained TCGdex MIT license supports metadata use; D1/E1's documented source
assessment remains the rights basis. License hash is pinned in inputs.json.
Artwork, rules text and embedded third-party prices are excluded from the package.
Private raw retention does not establish redistribution rights for those fields.

## First unmet gate and synthetic preservation

The existing collection importer `catalog_imports.Metadata.pokemon_dex` accepts
only #001–251. An exact 18-card bridge therefore rejects four supported canonical
IDs: **det1-2 Ludicolo #272, det1-3 Morelull #755, det1-9 Greninja #658,
det1-18 Slaking #289**. Snubbull #209 is within the existing ceiling.
[Gate diagnosis](../evidence/d1d-20261005/bridge-gate.json) and
[rejected full bridge input](../evidence/d1d-20261005/rejected-bridge-input.json)
retain the four validation errors. The diagnostic input uses the bridge-required
`unlimited` compatibility sentinel solely to expose the canonical-ID gate; it
is rejected and is not a validated edition claim or publication package.
The validated sealed metadata package has no collection bridge and is not published.

A **fresh generated synthetic SQLite root** was created at
`/Users/michaelfuscoletti/dex-private/d1d-20261005/synthetic-gate` using the supported
synthetic seed. Its copies, frozen goals, scan/photos and consumed reservation
were populated before the full-set attempt, including a frozen Original 151 goal.
The exact full bridge failed in the existing preview service before creating a
D1d journal or catalog record. [Preservation results](../evidence/d1d-20261005/synthetic-gate/preservation.json)
show all table rows, frozen goals and photo bytes unchanged. SQLite backup
restoration reproduced every baseline row/photo and passed integrity checking.
Baseline hashes/counts explicitly show which tables were populated; empty binder,
hunt or saved-research tables are not claimed as populated preservation proof.

**Stopped at that gate.** D1d verify, reviewed publication, publication idempotency,
identity-conflict exercise, publication rollback, catalog-growth frozen-goal check
and eligible successor-goal preview were not executed. Restoration checks qualify
the failed-preview boundary only. Existing regression tests separately exercise
import/bridge idempotency, identity conflicts, rollback/recovery, frozen membership,
explicit successors and retained hunt scope with earlier data/synthetic examples;
they do not qualify D1d publication. No browser-visible application behavior changed,
so no D1d browser walkthrough was needed or performed. PostgreSQL remains unqualified.

## Updated reconciliation

[New dated reconciliation](../evidence/d1d-20261005/reconciliation/per-set.json)
changes only the Detective Pikachu set row; D1c output/input lock remain unchanged.
[Series totals](../evidence/d1d-20261005/reconciliation/series-summary.json) and
[gaps](../evidence/d1d-20261005/reconciliation/gaps.json) distinguish complete
numbered metadata from blocked collection publication.

| Retained October 4 universe measure | D1d result |
|---|---:|
| Physical / digital sets | 205 / 15 |
| Complete numbered metadata sets | 13 |
| Absent physical numbered sets | 192 |
| Physical expected / reviewed numbered / gap | 21,484 / 1,216 / 20,268 |
| Combined expected / reviewed / gap | 23,964 / 1,216 / 22,748 |
| Normalized catalog records in reconciliation scope | 1,393 |
| Historical synthetic imported records / D1d imported records | 1,375 / 0 |
| Numbered sets with retained synthetic publication / pending | 12 / 1 |

Sun & Moon now has 18 reviewed numbered metadata identities and 17 absent sets;
its count gap is 2,899. These are source-coverage gains only. All variant totals
remain unknown/partial; the earlier 207 standard 151 memberships and 177 extra
151 variant gaps are unchanged. D1d adds 18 individually unknown relationships.
No owner installation coverage or complete all-era coverage is implied.

## Offline reproduction and checks

With locked dependencies available, from the repository:

```sh
uv run --no-sync python scripts/prepare_d1d.py --check
uv run --no-sync python scripts/reconcile_d1d.py --check
uv run --no-sync python scripts/reconcile_d1c.py --check
```

These verify the immutable input lock, response/header/transport hashes, all 18
identities, categories and registry mappings, 72-record cap, metadata schema,
precisely four bridge rejection errors and dated reconciliation. They use retained
bytes only. Missing/drifted private bytes are a blocker, not permission to reacquire.
Omitting `--check` regenerates derived output only after input verification.
**Do not rerun acquisition; its budget is closed.** The retained synthetic gate
script also refuses existing state/output. A new rehearsal boundary needs separately
selected fresh paths after the importer gate is repaired.

[Dated validation](history/2026-10-05-D1D-VALIDATION.md) records check results.
Application implementation is unchanged; focused importer/bridge/goal checks and
repository dependency, compilation, JavaScript, lint and formatting checks were run.
The final candidate and SHA-256 are under
`evidence/d1d-20261005/validation-final/` and preserve the inherited file scope.

**One exact next blocker:** extend the collection metadata/bridge canonical-ID
support beyond #251 to the retained 1,025-species registry, preserving vintage
#001–251 and Original 151 goal policies and unknown physical edition/finish.
Then restart the full 18-card reviewed publication and successor-goal rehearsal
from retained bytes on fresh synthetic state, with no new source requests.
