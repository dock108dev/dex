"""Share identical public/retained rows, preserving distinct publication conflicts."""

import json

from . import card_groups


def compact(data):
    groups = {}
    for row in data["cr_groups"]:
        if row[1] not in groups:
            groups[row[1]] = json.loads(row[-2])
    ranks = {}
    for sort, field in (("set", "set_name"), ("name", "name"), ("number", "collector_number")):
        ordered = sorted(
            groups.values(),
            key=lambda r: (
                card_groups._collector_number_key(r[field]) if sort == "number" else r[field].casefold(),
                r["set_name"].casefold(),
                card_groups._collector_number_key(r["collector_number"]),
                r["name"].casefold(),
                r["id"],
            ),
        )
        ranks[sort] = {r["id"]: i for i, r in enumerate(ordered)}
    remap = {
        (r[0], r[6]): tuple(ranks[s][r[1]] for s in ("set", "name", "number")) for r in data["cr_groups"]
    }
    data["cr_groups"] = [(*r[:6], *remap[r[0], r[6]], *r[9:]) for r in data["cr_groups"]]
    data["cr_grams"] = [(r[0], remap[r[0], r[1]][0], r[2]) for r in data["cr_grams"]]
    data["cr_match"] = [(r[0], *remap[r[0], r[1]], *r[4:]) for r in data["cr_match"]]
    for table, rows in data.items():
        if table == "cr_options":
            rows.sort()
            continue
        retained = {r[1:] for r in rows if r[0] == "retained"}
        public = {r[1:] for r in rows if r[0] == "public"}
        shared = retained & public
        data[table] = sorted(
            [("shared", *r) for r in shared]
            + [("public", *r) for r in public - shared]
            + [("retained", *r) for r in retained - shared]
            + [r for r in rows if r[0] not in {"retained", "public"}]
        )
    return data
