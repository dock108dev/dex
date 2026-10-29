"""Pure typed catalog records, literal identities, ordering and search postings."""

import hashlib
import json

from . import card_groups
from .catalog_read_schema import TABLES


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def grams(text):
    return {text[i : i + n] for n in (1, 2, 3) for i in range(len(text) - n + 1)}


def summary(group, published):
    children = group["_children"]
    parents = {r.get("parent_printing_id") for r in children if r.get("parent_printing_id")}
    physical = [r for r in children if r["id"] not in parents]
    group.update(
        variant_count=len(physical),
        published_variant_count=sum(r["id"] in published for r in physical),
        catalog_available=any(r["id"] in published for r in children),
    )
    return {field: group[field] for field in card_groups.SUMMARY_FIELDS}


def scopes(rows, public):
    """Share complete identity buckets; mixed visibility still gets independent grouping."""
    if len(public) == len(rows):
        return (("shared", rows),)
    original = (("retained", rows), ("public", public))
    fields = ("game_id", "set_id", "language", "collector_number")
    # The ordinary snapshot has unique literal IDs. Preserve legacy duplicate and
    # malformed-input semantics rather than selecting a representative for them.
    if len({row["id"] for row in rows}) != len(rows) or any(
        not all(isinstance(row.get(field), str) for field in fields) for row in rows
    ):
        return original
    public_ids = {row["id"] for row in public}
    private_keys = {tuple(row[field] for field in fields) for row in rows if row["id"] not in public_ids}
    shared, retained, visible = [], [], []
    for row in rows:
        if tuple(row[field] for field in fields) not in private_keys:
            shared.append(row)
        else:
            retained.append(row)
            if row["id"] in public_ids:
                visible.append(row)
    return tuple(
        (name, selected)
        for name, selected in (("retained", retained), ("public", visible), ("shared", shared))
        if selected
    )


def materialize(rows, pokemon, reviewed_aliases, metadata):
    """No database calls or write locks during grouping, ranking and gram construction."""
    data = {table: [] for table in TABLES}
    published = {r["id"] for r in rows if r["publication_state"] == r["set_publication_state"] == "published"}
    public = [r for r in rows if r["id"] in published and r["game_id"] in pokemon and r["language"] == "en"]
    selected_scopes = scopes(rows, public)
    option_groups, unresolved = [], []
    cards = {}
    gram_cache = {}
    word_cache = {}
    for child in rows:
        card = dict(metadata[child["id"]], language=child["language"], available=child["id"] in published)
        payload = encode(card)
        cards[child["id"]] = (card, payload, len(payload.encode()), digest(payload))
    for scope, selected in selected_scopes:
        built = card_groups.build_groups(selected, pokemon_game_ids=pokemon)
        for child in selected:
            card, payload, size, sha = cards[child["id"]]
            data["cr_species"].append(
                (
                    scope,
                    child["id"],
                    card["pokemon_dex"],
                    card["set_id"],
                    card["era"],
                    card["supertype"],
                    " ".join(card[key] or "" for key in ("name", "collector_number", "set_name")).casefold(),
                )
            )
            search = (
                " ".join(str(child.get(f) or "") for f in ("name", "set_name", "collector_number"))
                + " "
                + child.get("variant_label", "")
            ).casefold()
            data["cr_printings"].append(
                (
                    scope,
                    child["id"],
                    built["printing_to_group"].get(child["id"]),
                    int(child["id"] in published),
                    card.get("edition"),
                    card.get("finish"),
                    card.get("variant"),
                    search,
                    size,
                    payload,
                    sha,
                )
            )
        if len(selected_scopes) > 1:
            # Compaction assigns final cross-scope ranks once. Only the local
            # set rank is needed to correlate rows until that step.
            local = {group["id"]: i for i, group in enumerate(built["groups"])}
            ranks = {sort: local for sort in ("set", "name", "number")}
        else:
            ranks = {}
            for sort, field in (("set", "set_name"), ("name", "name"), ("number", "collector_number")):
                ordered = sorted(
                    built["groups"],
                    key=lambda r: (
                        card_groups._collector_number_key(r[field])
                        if sort == "number"
                        else r[field].casefold(),
                        r["set_name"].casefold(),
                        card_groups._collector_number_key(r["collector_number"]),
                        r["name"].casefold(),
                        r["id"],
                    ),
                )
                ranks[sort] = {r["id"]: i for i, r in enumerate(ordered)}
        postings = set()
        option_groups.extend((scope, group) for group in built["groups"])
        unresolved.extend((scope, record) for record in built["unresolved"])
        for group in built["groups"]:
            key = group["id"]
            payload = encode(summary(group, published))
            data["cr_groups"].append(
                (
                    scope,
                    key,
                    group["pokemon_dex"],
                    group["set_id"],
                    group["language"],
                    " ".join(group[f] for f in ("name", "set_name", "collector_number")).casefold(),
                    *(ranks[s][key] for s in ("set", "name", "number")),
                    len(payload.encode()),
                    payload,
                    digest(payload),
                )
            )
            gram_key = (key, tuple(child["id"] for child in group["_children"]))
            cached = gram_cache.get(gram_key)
            search_grams = set()
            for child in group["_children"]:
                card, payload, size, sha = cards[child["id"]]
                search = (
                    " ".join(group[f] for f in ("name", "set_name", "collector_number"))
                    + " "
                    + child.get("variant_label", "")
                ).casefold()
                data["cr_match"].append(
                    (
                        scope,
                        *(ranks[s][key] for s in ("set", "name", "number")),
                        child["id"],
                        group["pokemon_dex"],
                        group["set_id"],
                        group["language"],
                        child.get("edition"),
                        child.get("finish"),
                        child.get("variant"),
                        search,
                    )
                )
                data["cr_children"].append(
                    (
                        scope,
                        child["id"],
                        key,
                        int(child["id"] in published),
                        child.get("edition"),
                        child.get("finish"),
                        child.get("variant"),
                        search,
                        size,
                        payload,
                        sha,
                    )
                )
                if cached is None:
                    for word in search.split():
                        search_grams.update(word_tokens(word, word_cache))
                for field, value, label in [
                    ("set", group["set_id"], group["set_name"]),
                    ("language", group["language"], group["language"]),
                ] + [(f, child.get(f), child.get(f)) for f in ("edition", "finish", "variant")]:
                    if isinstance(value, str) and value:
                        postings.add((scope, field, value, key))
            if cached is None:
                cached = (
                    " ".join(sorted(search_grams))
                    + " "
                    + common_tokens(
                        " ".join(group[f] for f in ("name", "set_name", "collector_number")).casefold(),
                        word_cache,
                    )
                )
                gram_cache[gram_key] = cached
            data["cr_grams"].append((scope, ranks["set"][key], cached))
        data["cr_postings"].extend(sorted(postings))
        for alias, ids in card_groups.alias_inventory(selected).items():
            data["cr_aliases"].extend((scope, alias, key) for key in ids)
    # Option labels and evidence IDs follow each complete visible scope's original
    # group/evidence order, independently of the shared materialization partition.
    visible_scopes = ("shared",) if len(public) == len(rows) else ("retained", "public")
    for scope in visible_scopes:
        groups = [group for source, group in option_groups if source in {scope, "shared"}]
        groups.sort(
            key=lambda group: (
                group["set_name"].casefold(),
                card_groups._collector_number_key(group["collector_number"]),
                group["name"].casefold(),
                group["id"],
            )
        )
        options = {}
        for group in groups:
            for child in group["_children"]:
                for field, value, label in [
                    ("set", group["set_id"], group["set_name"]),
                    ("language", group["language"], group["language"]),
                ] + [(f, child.get(f), child.get(f)) for f in ("edition", "finish", "variant")]:
                    if isinstance(value, str) and value:
                        options.setdefault(field, {})[value] = label
        for field, values in options.items():
            for rank, (value, label) in enumerate(
                sorted(values.items(), key=lambda p: (p[1].casefold(), p[0]))
            ):
                data["cr_options"].append(
                    (scope, field, rank, value, label, len(encode(dict(value=value, label=label)).encode()))
                )
        records = sorted(
            (record for source, record in unresolved if source in {scope, "shared"}),
            key=lambda record: json.dumps(record, sort_keys=True),
        )
        for i, evidence in enumerate(records):
            payload = encode(evidence)
            data["cr_evidence"].append((scope, str(i), len(payload.encode()), payload, digest(payload)))
    # Retain literal reviewed candidates internally, without leaking request evidence publicly.
    for row in reviewed_aliases:
        data["cr_aliases"].append(
            ("reviewed", encode([row["game"], row["language"], row["alias"]]), row["identity_key"])
        )
    from .catalog_read_compact import compact

    if len(selected_scopes) == 1:
        for values in data.values():
            values.sort()
    else:
        data = compact(data)
    return data


def word_tokens(word, cache, *, positive=False):
    key = (positive, word)
    if key in cache:
        return cache[key]
    pieces = (
        {word[start:end] for start in range(len(word)) for end in range(start + 1, len(word) + 1)}
        if positive
        else grams(word)
    )
    prefix = "p" if positive else "g"
    result = frozenset(prefix + piece.encode().hex() for piece in pieces)
    if len(cache) >= 4096:
        cache.clear()
    # This temporary preparation cache is bounded and contains no authority.
    if len(word) <= 128:
        cache[key] = result
    return result


def common_tokens(text, cache):
    # Query tokens cannot span whitespace. Exact common-word substrings accelerate
    # positive matches; long words retain the complete gram/residual path.
    tokens = set()
    for word in text.split():
        if len(word) <= 24:
            tokens.update(word_tokens(word, cache, positive=True))
    return " ".join(sorted(tokens))
