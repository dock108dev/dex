# Image roles and private reference scope

Images do not establish ownership, quantity, exact qualification or destinations.
The canonical registry and catalog/copy IDs supply identity independently of art.

| Role | Binding | Available evidence and fallback |
| --- | --- | --- |
| Pokémon artwork | Canonical species `ndex:0001`–`ndex:0251` | Separate pinned PokeAPI official artwork mapping; missing/conflicting/blocked artwork leaves neutral fixed space, never a card scan |
| Card reference scan | Checked game/set/language/literal number/name/species group | 21,516 reviewed identities across 202 sets; standard TCGdex scans identify cards, independently of possession |
| Exact selected-child image | Group and explicitly requested child | No independently supported exact edition/finish assets retained; explicit unavailable, archived context preserved; selection stays null without a child |
| Private copy photo | Authoritative account/copy/scan-job/photo association | Same authorized serving rules as `/scan-photos/<id>/`; removal, expiry, undo, revocation and missing bytes prevent access; provisional JSON/URLs/paths confer no access |

`beta/image_mappings.py` reads the hash-pinned packaged mapping JSON. Its pure
functions require checked identity inputs. `beta/image_bindings.py` validates
catalog inputs against current metadata and rechecks account/generation before
returning descriptors. `image_bindings.enabled` also supplies remote-image
availability to the owned-reference adapter and private collection shell. Catalog
groups and English literal declarations use the same checked literal mapping index;
missing or duplicate identities stay unavailable. No owned-reference URL constructor
or normalized-name lookup remains. The active parity owned-reference adapter
reprojects and compares complete current collection state before accepting an overlay;
matching user ID alone is insufficient. Optional detail contains source IDs and gap reasons.
Descriptor fields are `role,bound_identity,precision,availability,image_url,width,
height,alt,source_id,reason`. `reference` means mapped URL, not successful load or
exact depiction. Private photo dimensions describe a 320×320 containment box;
intrinsic dimensions remain explicitly unavailable in that descriptor.

Authenticated local parity species slots consume only species artwork. Card
adapters consume group references. Links and selected child use canonical IDs,
independently of images. Shared rendering contains images in fixed space, escapes
alt text, loads lazily, decodes asynchronously and sends no referrer. Failed
compact images keep their neutral area and keyboard destination.

Public projections and staging omit remote artwork/reference descriptors and
origins. Existing authenticated staging photo policy remains available. One
effective local private `img-src` permits self, `assets.tcgdex.net` and
`raw.githubusercontent.com`; no wildcard. Explicit private no-store headers survive
security middleware. Outbound image URLs contain canonical asset IDs only.
Showing a private photo invokes no recognition/provider attempt or inventory write.

Reference descriptors are limited to authenticated local use. Software and metadata
licenses do not establish artwork redistribution permission. No image bytes are
bundled or exported, and there is no public scan catalog or acquisition schedule.
The [catalog](catalogs.md) remains all-era where indexed; unavailable art never removes
a card.

All 53 promo metadata identities retain per-card date evidence. Two early
release histories have secondary date reports plus first-party PSA year
corroboration; 12 later records have 2002 PSA catalog-year labels with unknown
exact release date; 39 dates remain unknown. Set date and numbering never label
the entire set through 2001. Missing date evidence does not remove a reference.

A constructed reference URL is not a successful load or proof of an exact edition.
Remote asset availability is not guaranteed. Failed images keep their neutral space
and accessible destination; tests use controlled image responses rather than
requiring external artwork hosts.


## Reference coverage

Card references are independent of possession or era. The hash-pinned
mapping contains 21,516 English reference identities across 202 sets from retained
TCGdex revision `99c994747cf7519a3e51166cc932de79a88bd4b3`. The finite reproducible
extractor is `scripts/extend_collection_images.py`. It keeps literal set/name/
number/species identity and records explicit application aliases for 151's `/165`
numbers, Detective Pikachu's `/18` numbers and the Minun Trainer Kit set title.
References expand image coverage, not published catalog metadata or exact variants.

Mapping coverage describes identity bindings, not a successful load of every remote
asset. A card with no provider image remains unavailable. No artwork bytes, prices,
rules text or private data are bundled or exported.

A current account-checked literal declaration can have an English card reference
without a catalog printing ID. Such artwork appears in Card details needed and
species references. Exact name, set, number and species must all match a single
reviewed mapping; conflicting, partial or approximate identities stay unavailable.
Artwork does not establish language, resolve catalog support or create a card tile,
copy or goal membership. Public/staging output still omits remote descriptors.

Card lists show readable Owned/Not owned badges and larger reference images.
Grey out unowned cards is an optional local visual preference, scoped to the
signed-in account and browser origin. It filters only unowned image color/opacity;
hover and keyboard focus reveal full color. Cards, labels, links, catalog scope,
counts and collection state remain unchanged. Unchecking restores full color.

## Image availability limits

Mapping counts describe retained identity bindings, not complete Pokémon card
coverage or successful loads of every remote URL. Remote availability and detail
sharpness can vary; the interface must retain an honest unavailable state.

EX Trainer Kit 2 — Minun Vulpix #7 has no retained provider image. A substitute
must match that exact card identity and its source permissions. An unavailable
asset does not authorize bypassing a denied route or collecting image bytes.
Higher-resolution references require the same identity binding and fallback policy.

## Hunter result and review bindings

Hunter HTTP projections resolve returned printing IDs through `catalog_images`.
Results, unresolved candidates, lot proposals and included-review identities use
those checked descriptors. Optional descriptors/labels are omitted when needed to
retain the existing 2 MiB response limit; the UI keeps a neutral fixed image slot.
No seller-image URLs are constructed. Browser qualification uses controlled image
responses and does not establish remote availability or seller-photo evidence.
