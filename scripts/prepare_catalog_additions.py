"""Prepare complete retained enumeration and additive numbered-parent packages."""

import hashlib

from prepare_broad_catalog import ARCHIVE_SHA256, PIN, encode, read_retained
from prepare_broad_publication import load_inventory, package_files


def prepare(inventory, selected, public, source):
    code = selected["set"]
    info = next(s for s in inventory["sets"] if s["provider_set_id"] == code)
    cards = [c for c in inventory["cards"] if c["provider_set_id"] == code]
    if info["gaps"] or any(c["disposition"] != "resolved" for c in cards):
        raise ValueError("Unresolved source enumeration")
    maps = {
        (r["provider"], r["entity_kind"], r["external_id"]): r["internal_id"]
        for r in public["external_mappings"]
    }
    source_set_key = code if ("tcgdex:en", "set", code) in maps else code.replace(".", "-")
    sid = maps["tcgdex:en", "set", source_set_key]
    setrow = next(s for s in public["catalog_sets"] if s["id"] == sid)
    represented, missing, enumeration = {}, [], []
    by_numbered = {}
    for (provider, kind, external), pid in maps.items():
        if provider == "tcgdex:en" and kind == "printing":
            by_numbered.setdefault(external.split(":", 1)[0], {})[external] = pid
    for c in cards:
        if c["category"] == "Pokemon" and len(c["species"]) != 1:
            raise ValueError("Unresolved species")
        n = c["species"][0] if c["category"] == "Pokemon" else None
        record = dict(
            external_id=c["external_id"],
            number=c["number"],
            name=c["name"],
            edition=None,
            finish=None,
            variant=None,
            metadata=dict(
                pokemon_dex=n,
                dex_eligible=n is not None,
                supertype={"Pokemon": "Pokémon", "Trainer": "Trainer", "Energy": "Energy"}[c["category"]],
                rarity=c.get("rarity") or "Unknown",
            ),
        )
        enumeration.append(record)
        bindings = by_numbered.get(c["external_id"], {})
        if bindings:
            represented[c["external_id"]] = bindings
        else:
            missing.append(record)
    if sorted(c["external_id"] for c in missing) != sorted(selected["external_ids"]):
        raise ValueError("Current represented/missing partition changed")
    p = dict(
        schema_version="dex-catalog-additions-v1",
        game="pokemon",
        provider="tcgdex",
        version="c1-additive-" + PIN[:12] + "-numbered-v1",
        source_time=source["cutoff"],
        source_members={
            c["external_id"]: dict(path=c["source_file"], sha256=c["source_sha256"]) for c in cards
        },
        set_id=sid,
        set_sha256=hashlib.sha256(encode(setrow).encode()).hexdigest(),
        source_set_key=source_set_key,
        set_key=code.replace(".", "-"),
        set_name=info["name"],
        language="en",
        aliases=[],
        source_url=f"https://codeload.github.com/tcgdex/cards-database/tar.gz/{PIN}",
        source_sha256=ARCHIVE_SHA256,
        metadata_permission="MIT; Copyright (c) 2021 TCGdex; retained evidence/d6-20261005/TCGDEX_LICENSE.txt",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=len(cards),
        cards=missing,
        enumeration=enumeration,
        represented=represented,
    )
    return dict(
        set_id="tcgdex:en:" + p["set_key"],
        language="en",
        era=info["era"],
        medium="physical",
        release_status="released" if info["release_date"] <= source["cutoff"][:10] else "uncertain",
        source_url=p["source_url"],
        source_time=source["cutoff"],
        source_sha256=ARCHIVE_SHA256,
        evidence_class="retained-real-source",
        enumerated_ids=sorted(c["external_id"] for c in enumeration),
        enumeration_complete=True,
        expected_target_count=len(cards),
        catalog_policy="english-physical-all",
        package=p,
    )


def prepare_batch(repo, inventory_dir, selection, public, output):
    inventory = load_inventory(inventory_dir)
    parsed, members, failures, sources = read_retained(repo)
    assert sources["tcgdex-archive"]["retrieved_at"] == selection["source"]["cutoff"]
    assert (
        hashlib.sha256((inventory_dir / "summary.json").read_bytes()).hexdigest()
        == selection["source"]["summary_sha256"]
    )
    output.mkdir(exist_ok=False)
    results, held = [], []
    for selected in selection["mixed_existing_sets"]:
        try:
            assert members[selected["source_file"]]["sha256"] == selected["source_sha256"]
            a = prepare(inventory, selected, public, selection["source"])
            files = package_files(inventory_dir, a)
            assert files == package_files(
                inventory_dir, prepare(inventory, selected, public, selection["source"])
            )
            path = output / selected["set"]
            path.mkdir()
            for name, raw in files.items():
                (path / name).write_text(raw)
            results.append(
                dict(
                    set=selected["set"],
                    records=len(a["package"]["cards"]),
                    represented=len(a["package"]["represented"]),
                    full=len(a["package"]["enumeration"]),
                    files={k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()},
                )
            )
        except (ValueError, AssertionError, KeyError) as exc:
            held.append(dict(set=selected["set"], reason=str(exc)))
    return dict(
        status="PASS" if not held else "PARTIAL",
        packages=results,
        exclusions=held,
        archive_loads=1,
        archive_members_verified=len(members),
        literal_parse_gaps=len(failures),
        prepared_sets=len(results),
        records=sum(r["records"] for r in results),
        represented=sum(r["represented"] for r in results),
        full=sum(r["full"] for r in results),
        provider_operations=0,
        customer_writes=0,
    )
