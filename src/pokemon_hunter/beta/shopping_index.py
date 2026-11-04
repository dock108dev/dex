"""Operation-local indexed Shopping reads; no seller data or assessments are cached.

The ordinary account read boundary owns the immutable catalog snapshot, account
revision and final publication checks. Legacy roots without read infrastructure
retain their compatibility path; stale/prepared roots never fall back to it.
"""

import re
from contextvars import ContextVar
from functools import wraps

from . import account_read_build as builds
from . import account_read_context, discovery_matching, store

_current = ContextVar("shopping_index", default=None)


def words(text):
    # Python's Unicode IGNORECASE treats these as the same letters as ASCII.
    text = discovery_matching.literal(text).translate(str.maketrans("İıſK", "iisk"))
    return re.findall(r"\w+", text.casefold())


def name_records(rows):
    return sorted(
        {
            (next(iter(words(name)), ""), name, row["id"], ordinal)
            for ordinal, row in enumerate(rows)
            for name in discovery_matching.names(row) or ("",)
        }
    )


def current(actor):
    value = _current.get()
    return value if value is not None and value.active and value.actor == actor else None


def known_published_pokemon(ids):
    """Reuse only identities already read inside this authorized catalog snapshot."""
    read = _current.get()
    if read is None or not read.active or not read.metadata.keys() >= ids:
        return None
    return {p["id"]: p for p in read.published(read.metadata[k] for k in ids) if p["game_id"] in read.games}


def indexed(fn):
    @account_read_context.read
    def admitted(actor, build, state, raw, *, args, kwargs, holder):
        value = Read(actor, build, state)
        holder.append(value)
        token = _current.set(value)
        try:
            with store.read_authority(actor), discovery_matching.local_evidence():
                return fn(actor, *args, **kwargs)
        finally:
            value.active = False
            _current.reset(token)

    @wraps(fn)
    def wrapped(actor, *args, **kwargs):
        if current(actor) is not None:
            return fn(actor, *args, **kwargs)
        if not store.rows("SELECT 1 FROM sqlite_master WHERE type='table' AND name='account_read_schema'"):
            return fn(actor, *args, **kwargs)
        holder = []
        result = admitted(actor, args=args, kwargs=kwargs, holder=holder)
        for check in holder[0].publication_checks:
            check()
        return result

    return wrapped


class Read:
    def __init__(self, actor, build, state):
        self.actor, self.build, self.state = actor, build, state
        self.active = True
        self.publication_checks = []
        self.metadata = {}
        self.named = {}
        self.order = {}
        self.candidate_rows = None
        self._games = None
        self._aliases = None
        self.species_rows = {}

    def printings(self, ids):
        ids = set(ids)
        missing = ids - self.metadata.keys()
        if missing:
            rows = store.rows(
                "SELECT a.id,a.payload,a.sha,(SELECT MIN(ordinal) FROM ar_shopping_names n WHERE n.build=a.build AND n.printing_id=a.id) AS ordinal FROM ar_catalog a WHERE a.build=%s AND a.id IN (SELECT value FROM json_each(%s))",
                [self.build, builds.encode(sorted(missing))],
            )
            self.metadata.update({r["id"]: builds.decode(r) for r in rows})
            self.order.update({r["id"]: r["ordinal"] for r in rows})
        return [self.metadata[key] for key in sorted(ids) if key in self.metadata]

    def matching(self, text):
        text = discovery_matching.literal(text)
        if text not in self.named:
            anchors = sorted(set(words(text)) | {""})
            names = store.rows(
                "SELECT DISTINCT name FROM ar_shopping_names WHERE build=%s AND anchor IN (SELECT value FROM json_each(%s))",
                [self.build, builds.encode(anchors)],
            )
            matched = [r["name"] for r in names if discovery_matching.name_spans({"name": r["name"]}, text)]
            found = (
                store.rows(
                    "SELECT a.id,a.payload,a.sha,MIN(n.ordinal) AS ordinal FROM ar_shopping_names n INDEXED BY ar_shopping_name JOIN ar_catalog a ON a.build=n.build AND a.id=n.printing_id WHERE n.build=%s AND n.name IN (SELECT value FROM json_each(%s)) GROUP BY a.id ORDER BY ordinal",
                    [self.build, builds.encode(matched)],
                )
                if matched
                else []
            )
            self.metadata.update({r["id"]: builds.decode(r) for r in found})
            self.order.update({r["id"]: r["ordinal"] for r in found})
            self.named[text] = [self.metadata[r["id"]] for r in found]
        return self.named[text]

    def published(self, rows):
        return [
            r
            for r in rows
            if r.get("publication_state", "published")
            == r.get("set_publication_state", "published")
            == "published"
        ]

    def proposals(self, text):

        return self.supported(self.matching(text))

    def supported(self, rows):
        from .lot_calculator import SETS, current_species_printing

        rows = self.published(rows)
        games = self.games
        goals = None
        result = []
        for row in rows:
            if row["game_id"] not in games:
                continue
            if row["set_name"] in SETS or current_species_printing(row):
                result.append(row)
            else:
                if goals is None:
                    goals = {
                        r["printing_id"]
                        for r in store.rows(
                            "SELECT DISTINCT printing_id FROM ar_goal_printings WHERE user_id=%s",
                            [self.actor.user_id],
                        )
                    }
                if row["id"] in goals:
                    result.append(row)
        # Preserve catalog order across the complete matching family.
        return sorted(result, key=lambda p: self.order.get(p["id"], 0))

    def species(self, number):
        if number in self.species_rows:
            return self.species_rows[number]
        return builds.decode(
            store.rows(
                "SELECT payload,sha FROM ar_species WHERE user_id=%s AND id=%s",
                [self.actor.user_id, str(number)],
            )[0]
        )

    def variants(self, key):
        rows = store.rows(
            "SELECT id,payload,sha,published FROM cr_children WHERE build=%s AND scope IN ('retained','shared') AND group_id=%s AND EXISTS(SELECT 1 FROM ar_membership m WHERE m.user_id=%s AND m.id=group_id AND m.available=1) ORDER BY id",
            [self.build, key, self.actor.user_id],
        )
        result = []
        for row in rows:
            p = builds.decode(row)
            result.append(
                dict(
                    id=p["id"],
                    label=p.get("variant_label")
                    or " · ".join(filter(None, [p.get("edition"), p.get("finish"), p.get("variant")])),
                    available=bool(row["published"]),
                )
            )
        return result

    @property
    def games(self):
        if self._games is None:
            self.common()
        return self._games

    @property
    def aliases(self):
        if self._aliases is None:
            self.common()
        return self._aliases

    def common(self):
        rows = store.rows(
            "SELECT 'game' AS kind,id,id AS value FROM games WHERE game_key='pokemon' UNION ALL SELECT 'alias',internal_id,external_id FROM external_mappings WHERE provider='legacy' AND entity_kind='set'"
        )
        self._games = {r["id"] for r in rows if r["kind"] == "game"}
        self._aliases = {r["id"]: r["value"] for r in rows if r["kind"] == "alias"}

    def artwork(self, catalog):
        from . import image_bindings

        if any(self.metadata.get(p["id"]) != p for p in catalog):
            raise ValueError("Image catalog differs from authorized metadata")
        if not catalog or not image_bindings.enabled():
            return {}
        found = store.rows(
            "SELECT c.id,a.payload,a.sha,g.payload AS group_payload,g.sha AS group_sha FROM cr_children c JOIN ar_artwork a ON a.user_id=%s AND a.id=c.group_id JOIN ar_groups g ON g.user_id=a.user_id AND g.id=a.id WHERE c.build=%s AND c.scope IN ('retained','shared') AND c.id IN (SELECT value FROM json_each(%s))",
            [self.actor.user_id, self.build, builds.encode([p["id"] for p in catalog])],
        )
        result = {}
        for row in found:
            group = builds.decode(dict(payload=row["group_payload"], sha=row["group_sha"]))
            result[row["id"]] = dict(
                builds.decode(row),
                name=group["name"],
                set_name=group["set_name"],
                number=group["collector_number"],
                pokemon_dex=group["pokemon_dex"],
            )
        return result

    def goal(self, key, species=None):
        rows = store.rows(
            "SELECT g.payload,g.sha,(SELECT COUNT(*) FROM ar_goal_items i WHERE i.user_id=g.user_id AND i.goal_id=g.id) AS total,(SELECT COUNT(*) FROM ar_goal_items i WHERE i.user_id=g.user_id AND i.goal_id=g.id AND i.status='owned') AS satisfied,s.payload AS species_payload,s.sha AS species_sha FROM ar_goals g LEFT JOIN ar_species s ON s.user_id=g.user_id AND s.id=%s WHERE g.user_id=%s AND g.id=%s",
            [str(species) if species else "", self.actor.user_id, key],
        )
        if not rows:
            from django.http import Http404

            raise Http404
        if species and rows[0]["species_payload"]:
            self.species_rows[species] = builds.decode(
                dict(payload=rows[0]["species_payload"], sha=rows[0]["species_sha"])
            )
        return dict(builds.decode(rows[0]), total=rows[0]["total"], satisfied=rows[0]["satisfied"])

    def detail(self, key, selected_child=None):
        from django.http import Http404

        found = store.rows(
            "SELECT payload,sha FROM ar_groups WHERE user_id=%s AND id=%s AND (available=1 OR present=1 OR recorded>0)",
            [self.actor.user_id, key],
        )
        if not found:
            raise Http404
        children = store.rows(
            "SELECT id,payload,sha,published FROM cr_children WHERE build=%s AND scope IN ('retained','shared') AND group_id=%s ORDER BY id",
            [self.build, key],
        )
        variants = [dict(builds.decode(r), available=bool(r["published"])) for r in children]
        selected = next((v for v in variants if v["id"] == selected_child), None)
        if selected_child and selected is None:
            raise Http404
        return dict(group=builds.decode(found[0]), variants=variants, selected_child=selected)

    def candidate_data(self, choices, scope):
        from . import collection_goals

        rows = list(self.candidate_rows or [])
        if choices.printing_id:
            rows = list({p["id"]: p for p in [*rows, *self.printings([choices.printing_id])]}.values())
        definition = scope["definition"] if scope else None
        frozen = (
            {pid: item.get("pokemon_dex") for item in definition["items"] for pid in item["printing_ids"]}
            if scope
            else {}
        )
        rows = [
            p
            for p in rows
            if (p["id"] in frozen if scope else True)
            and (self.published([p]) or scope and scope.get("kind") in collection_goals.KINDS)
        ]
        cards = {
            p["id"]: dict(
                p["attributes"],
                printing_id=p["id"],
                set_id=self.aliases.get(p["set_id"], p["set_id"]),
                set=p["set_name"],
                owned=False,
                exact_printing_owned=False,
            )
            for p in rows
        }
        pokedex = {}
        if choices.collection_intent:
            from .shopping_intent import _targets

            raw = dict(scope=choices.focus)
            if choices.goal_id:
                raw.update(goal=choices.goal_id, version=choices.goal_version)
            missing = {r["species"] for r in _targets(self.actor, raw)["targets"]}
            for p in rows:
                card = cards[p["id"]]
                if scope and scope.get("kind") in collection_goals.KINDS:
                    card["pokemon_dex"] = frozen[p["id"]]
                card["dex_eligible"] = card.get("pokemon_dex") in missing
            return dict(
                catalog=rows,
                cards=cards,
                pokedex={str(n): {"dex_owned": n not in missing} for n in range(1, 252)},
            )
        if choices.intent == "missing":
            species = definition["policy"] == "species" if scope else choices.missing_basis == "species"
            if scope:
                copies = store.rows(
                    "SELECT c.printing_id,p.unresolved_fields,c.provisional_identity,p.attributes FROM owned_copies c JOIN printings p ON p.id=c.printing_id WHERE c.user_id=%s AND c.state='active' AND c.printing_id IN (SELECT value FROM json_each(%s))",
                    [self.actor.user_id, builds.encode(list(frozen))],
                )
                import json

                if scope.get("kind") not in collection_goals.KINDS:
                    available = {
                        r["id"]
                        for r in store.rows(
                            "SELECT id FROM cr_printings WHERE build=%s AND scope IN ('retained','shared') AND published=1 AND id IN (SELECT value FROM json_each(%s))",
                            [self.build, builds.encode([c["printing_id"] for c in copies])],
                        )
                    }
                    copies = [c for c in copies if c["printing_id"] in available]
                exact = {
                    c["printing_id"]
                    for c in copies
                    if not json.loads(c["unresolved_fields"] or "[]")
                    and not json.loads(c["provisional_identity"] or "{}").get("unresolved_fields")
                }
                owned = (
                    exact
                    if definition["policy"] == "exact" or scope.get("kind") in collection_goals.KINDS
                    else {c["printing_id"] for c in copies}
                )
                present = set()
                for c in copies:
                    attr = json.loads(c["attributes"])
                    n = (
                        frozen[c["printing_id"]]
                        if scope.get("kind") in collection_goals.KINDS
                        else attr.get("pokemon_dex")
                    )
                    if c["printing_id"] in owned and type(n) is int and 1 <= n <= 251:
                        present.add(n)
                if scope.get("kind") in collection_goals.OWNERSHIP_KINDS:
                    present = set(definition["owned_species"])
                for p in rows:
                    card = cards[p["id"]]
                    card["owned"] = p["id"] in owned
                    if scope.get("kind") in collection_goals.KINDS and definition["policy"] != "exact":
                        card["pokemon_dex"] = frozen[p["id"]]
                        card["dex_eligible"] = True
                    elif species:
                        card["dex_eligible"] = (
                            type(card.get("pokemon_dex")) is int and 1 <= card["pokemon_dex"] <= 251
                        )
                pokedex = {str(n): {"dex_owned": n in present} for n in range(1, 252)}
            elif species:
                found = store.rows(
                    "SELECT id,json_extract(summary,'$.current_present') AS present FROM ar_species WHERE user_id=%s",
                    [self.actor.user_id],
                )
                pokedex = {r["id"]: {"dex_owned": bool(r["present"])} for r in found}
                for c in cards.values():
                    c["dex_eligible"] = bool(c.get("dex_eligible") and str(c.get("pokemon_dex")) in pokedex)
            else:
                owned = {
                    r["printing_id"]
                    for r in store.rows(
                        "SELECT DISTINCT printing_id FROM ar_copies WHERE user_id=%s AND current=1 AND exact=1 AND printing_id IN (SELECT value FROM json_each(%s))",
                        [self.actor.user_id, builds.encode(list(cards))],
                    )
                }
                for key, c in cards.items():
                    c["exact_printing_owned"] = key in owned
        return dict(catalog=rows, cards=cards, pokedex=pokedex)
