"""Reviewed metadata publication through the existing collection catalog service."""

from . import canonical_species, store
from . import catalog_imports as cat
from . import collection as inv


def validate(package, bridge):
    printings = {r["id"]: r for r in package["printings"]}
    raw = bridge["package"]
    p = cat.validate(raw)
    if p["game"] != "pokemon" or p["language"] != "en":
        raise ValueError("Bridge requires reviewed English Pokémon metadata")
    if len(bridge["links"]) != len(p["cards"]):
        raise ValueError("Bridge must map every incoming card")
    links = {r["external_id"]: r["printing_id"] for r in bridge["links"]}
    if len(links) != len(p["cards"]) or len(set(links.values())) != len(links):
        raise ValueError("Repeated bridge mapping")
    # Null edition is explicit unknown. Legacy unlimited bridges retain their
    # reviewed values; provider variant labels never fill physical attributes.
    for card in p["cards"]:
        r = printings.get(links.get(card["external_id"]))
        if not r or r["expansion_id"] != bridge["expansion_id"]:
            raise ValueError("Bridge printing/expansion missing")
        if r["species_id"]:
            number = int(r["species_id"].split(":")[1])
            if canonical_species.require(number) != r["species_id"] or r["category"] != "pokemon":
                raise ValueError("Bridge canonical species/category conflict")
        expected = dict(
            pokemon_dex=int(r["species_id"].split(":")[1]) if r["species_id"] else None,
            dex_eligible=r["category"] == "pokemon",
            supertype={"pokemon": "Pokémon", "trainer": "Trainer", "energy": "Energy"}.get(r["category"]),
            rarity=r["rarity"] or "Unknown",
        )
        if (
            any(card[k] != r[k] for k in ("number", "name", "finish", "variant"))
            or card.get("metadata") != expected
            or card["edition"] not in {None, "unlimited"}
        ):
            raise ValueError("Bridge metadata/category/canonical identity conflict")
        mappings = [
            m
            for m in package["mappings"]
            if m["kind"] == "printings"
            and m["internal_id"] == r["id"]
            and m["external_id"] == card["external_id"]
            and m["provider"] == p["provider"]
            and m["language"] == p["language"]
        ]
        if not mappings:
            raise ValueError("Bridge requires explicit external identity mapping")
    return p, links


def preview(actor, package):
    result = []
    for bridge in package["bridges"]:
        p, links = validate(package, bridge)
        op = cat.preview(actor, p)
        if op["preview"]["archived"]:
            raise ValueError("Bridge cannot implicitly archive existing collection printings")
        setrow, rows = cat.rows_for(p)
        expansion_sources = [
            m
            for m in package["mappings"]
            if m["kind"] == "expansions"
            and m["internal_id"] == bridge["expansion_id"]
            and m["provider"] == p["provider"]
            and m["language"] == p["language"]
        ]
        if len(expansion_sources) != 1:
            raise ValueError("Bridge requires one explicit provider expansion mapping")
        expansion_mapping = dict(
            provider=p["provider"] + ":" + p["language"],
            external_id=expansion_sources[0]["external_id"],
            internal_id=setrow["id"],
        )
        check_expansion_mapping(expansion_mapping)
        mapped = [
            {"printing_id": links[c["external_id"]], "catalog_id": r["id"], "external_id": c["external_id"]}
            for c, r in zip(p["cards"], rows, strict=True)
        ]
        for link in mapped:
            old = store.rows(
                "SELECT catalog_id FROM sealed_bridges WHERE printing_id=%s", [link["printing_id"]]
            )
            if old and old[0]["catalog_id"] != link["catalog_id"]:
                raise ValueError("Bridge identity cannot be remapped")
        result.append(
            dict(
                import_id=op["id"], mappings=mapped, expansion_mapping=expansion_mapping, impact=op["preview"]
            )
        )
    return result


def check_expansion_mapping(m):
    old = store.rows(
        "SELECT internal_id FROM external_mappings WHERE provider=%s AND entity_kind='set' AND external_id=%s",
        [m["provider"], m["external_id"]],
    )
    if old and old[0]["internal_id"] != m["internal_id"]:
        raise ValueError("Provider expansion identity already maps to a different collection set")


def transition(actor, bridges, action):
    for bridge in bridges:
        m = bridge["expansion_mapping"]
        check_expansion_mapping(m)
        cat.transition(actor, bridge["import_id"], action)
        if action == "publish":
            inv.execute(
                "INSERT INTO external_mappings VALUES(%s,'set',%s,%s) ON CONFLICT DO NOTHING",
                [m["provider"], m["external_id"], m["internal_id"]],
            )
            for link in bridge["mappings"]:
                inv.execute(
                    "INSERT INTO sealed_bridges VALUES(%s,%s,%s) ON CONFLICT(printing_id) DO NOTHING",
                    [link["printing_id"], link["catalog_id"], bridge["import_id"]],
                )
