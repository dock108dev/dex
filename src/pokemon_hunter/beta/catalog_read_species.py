"""Public species selectors preserve the V1 phrase, numeric and canonical-name rules."""

from . import canonical_species, public_catalog, store


def summaries(build, token, raw):
    from .catalog_read_queries import paging, url

    page, size = paging(raw, public_catalog.FILTERS)
    if raw.get("region", "") not in {"", "kanto", "johto"}:
        raise ValueError("Choose Kanto or Johto")
    conditions, params = ["build=%s", "scope IN ('public','shared')"], [build]
    for field in ("set", "era", "type"):
        if raw.get(field):
            column = {"set": "set_id", "era": "era", "type": "supertype"}[field]
            conditions.append(f"{column}=%s")
            params.append(raw[field])
    if raw.get("region"):
        conditions.append("species BETWEEN %s AND %s")
        params.extend([1, 151] if raw["region"] == "kanto" else [152, 251])
    query = raw.get("q", "").strip().casefold()
    numeric = query.removeprefix("#")
    numeric_value = int(numeric) if numeric.isdecimal() else None
    if query:
        conditions.append("(instr(search,%s)>0 OR species=%s)")
        params.extend(
            [query, numeric_value if numeric_value is not None and 1 <= numeric_value <= 251 else -1]
        )
    matches = (
        {
            r["species"]
            for r in store.rows(
                "SELECT DISTINCT species FROM cr_species INDEXED BY cr_public_species WHERE "
                + " AND ".join(conditions),
                params,
            )
        }
        if any(raw.get(f) for f in public_catalog.FILTERS)
        else set()
    )
    registry = canonical_species.registry()
    has_filter = any(raw.get(f) for f in ("set", "era", "type"))
    numbers = [
        n
        for n in range(1, 252)
        if (not raw.get("region") or raw["region"] == ("kanto" if n <= 151 else "johto"))
        and (not has_filter or n in matches)
        and (not query or n in matches or query in registry[n]["name"].casefold() or n == numeric_value)
    ]
    total = len(numbers)
    numbers = numbers[(page - 1) * size : page * size]
    counts, groups = {}, {}
    if numbers:
        placeholders = ",".join(["%s"] * len(numbers))
        counts = {
            r["species"]: r["n"]
            for r in store.rows(
                "SELECT species,COUNT(*) AS n FROM cr_species INDEXED BY cr_public_species WHERE build=%s AND scope IN ('public','shared') AND supertype='Pokémon' AND species IN ("
                + placeholders
                + ") GROUP BY species",
                [build, *numbers],
            )
        }
        groups = {
            r["species"]: r["n"]
            for r in store.rows(
                "SELECT species,COUNT(*) AS n FROM cr_groups WHERE build=%s AND scope IN ('public','shared') AND species IN ("
                + placeholders
                + ") GROUP BY species",
                [build, *numbers],
            )
        }
    return dict(
        species=[
            dict(
                dex=n,
                name=registry[n]["name"],
                region="kanto" if n <= 151 else "johto",
                printing_count=counts.get(n, 0),
                group_count=groups.get(n, 0),
                url=url(f"species/{n}/card-groups/", token),
            )
            for n in numbers
        ],
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
    )
