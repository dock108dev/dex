"""All-era local Hunter identity/reference batches; no acquisition or persistence.

Catalog availability limits matches, never provider query scope. These minimal
HUNT-02/03 adapters reuse Shopping's admission, literal identity and arithmetic.
They are also the local matching boundary for LOT-01's future reviewed contents;
a whole lot never receives the value of one matching single.
"""

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from pokemon_hunter.pricing import money as provider_money

from . import collection, discovery_comparison, discovery_matching, hunter_ranking, lot_calculator, store
from . import shopping_math as math
from .discovery_search import canonical_query

MAX_ROWS = 400
STATUSES = ("priced", "conditional", "ambiguous", "unmatched", "unpriced", "unsupported")


def _tokens(value):
    return frozenset(re.findall(r"\w+", discovery_matching.literal(value).casefold()))


class IdentityIndex:
    """Narrow by published name/set aliases and collector-number numerators.

    Names remain literal and siblings remain distinct. Token membership is only
    a narrowing optimization, never identity evidence or a first-match choice.
    """

    def __init__(self, printings):
        self.printings = printings
        self.names = {}
        self.by_token = defaultdict(set)
        self.by_set_token = defaultdict(set)
        self.by_number = defaultdict(set)
        set_tokens, number_keys = {}, {}
        for index, printing in enumerate(printings):
            aliases = tuple(_tokens(name) for name in discovery_matching.names(printing))
            self.names[index] = aliases
            for tokens in aliases:
                for token in tokens:
                    self.by_token[token].add(index)
            if printing["set_id"] not in set_tokens:
                set_tokens[printing["set_id"]] = frozenset(
                    token for name in discovery_matching.set_names(printing) for token in _tokens(name)
                )
            for token in set_tokens[printing["set_id"]]:
                self.by_set_token[token].add(index)
            number = printing["collector_number"]
            if number not in number_keys:
                number_keys[number] = discovery_matching.number_key(number)[0]
            self.by_number[number_keys[number]].add(index)
        # Each literal name needs only its rarest token as an index anchor. A
        # common suffix such as "ex" must not scan every indexed ex card per offer.
        anchors = defaultdict(set)
        for index, aliases in self.names.items():
            for tokens in aliases:
                if tokens:
                    anchor = min(tokens, key=lambda token: (len(self.by_token[token]), token))
                    anchors[anchor].add(index)
        self.by_token = anchors

    def candidates(self, clues):
        tokens = _tokens(canonical_query(clues["text"]))
        possible = set()
        for token in tokens:
            possible.update(self.by_token.get(token, ()))
        named = {
            index for index in sorted(possible) if any(name and name <= tokens for name in self.names[index])
        }
        longest_names = {
            p["id"]
            for p in discovery_matching.literal_candidates(
                [self.printings[index] for index in sorted(named)], clues["text"]
            )
        }
        named = {index for index in named if self.printings[index]["id"] in longest_names}
        set_possible = set()
        for token in tokens:
            set_possible.update(named.intersection(self.by_set_token.get(token, ())))
        set_matches = {
            index
            for index in named & set_possible
            if discovery_matching.set_claimed(self.printings[index], clues["text"])
        }
        narrowed = set_matches or named
        number_matches = set()
        for index in narrowed:
            for number in discovery_matching.number_claims(self.printings[index], clues["text"]):
                number_matches.update(
                    narrowed.intersection(self.by_number.get(discovery_matching.number_key(number)[0], ()))
                )
        # A failed number/set clue keeps plausible names for explicit diagnostics;
        # only the later literal evidence checks can establish a printing.
        narrowed = (narrowed & number_matches) or narrowed
        return [self.printings[index] for index in sorted(narrowed)]


class ReferenceIndex:
    """Index admitted records without replacing lifecycle or guide selection."""

    def __init__(self, records):
        self.status = getattr(records, "status", "active_snapshot")
        self.snapshots = defaultdict(list)
        self.legacy = defaultdict(list)
        for record in records:
            if "_snapshot_version" in record:
                self.snapshots[record.get("printing_id")].append(record)
            else:
                self.legacy[record.get("card_id")].append(record)

    def for_printing(self, printing):
        legacy_id = json.loads(printing["provenance"]).get("legacy_id")
        return lot_calculator.SnapshotRecords(
            self.snapshots.get(printing["id"], []) + self.legacy.get(legacy_id, []), self.status
        )


def _status(row):
    if row["discovery_kind"] != "single":
        return "unsupported"
    if row["classification"] == "comparable":
        return "priced"
    if row["classification"] == "conditional":
        return "conditional"
    if row["proposed_identity"]:
        return "unpriced"
    if row["identity_candidates_total"]:
        return "ambiguous"
    return "unmatched"


def _money(raw):
    value = provider_money(raw, "USD")
    if value is None:
        return None
    try:
        return math.money(math.amount(format(value, "f")))
    except ValueError:
        return None


def compare(actor, raw_rows, *, now=None):
    """Compare at most two 200-summary pages against one authorized local batch.

    Results are provider-content-bearing temporary values. The service must keep
    them account/session-bound and reread this adapter on publication/reopening
    so source withdrawal/expiry never survives via cached derived amounts.
    """
    store.verified(actor)
    if not isinstance(raw_rows, list) or len(raw_rows) > MAX_ROWS:
        raise ValueError("Hunter comparison requires at most 400 received summaries")
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Hunter comparison observation time must be aware")
    generation = collection.generation(actor)
    catalog = collection.catalog(actor, include_archived=True)
    pokemon_games = {r["id"] for r in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    printings = [p for p in catalog if p["game_id"] in pokemon_games]
    identities = IdentityIndex(printings)
    by_printing = {p["id"]: p for p in printings}
    records = lot_calculator.retained_records()
    references = ReferenceIndex(records)
    rows = discovery_comparison._project(
        actor,
        raw_rows,
        printings,
        records,
        now=now,
        candidates_for=identities.candidates,
        records_for=references.for_printing,
        artwork={},
        include_unsupported=True,
    )
    by_id = {raw.get("itemId"): raw for raw in reversed(raw_rows)}
    for row in rows:
        raw = by_id[row["item_id"]]
        subtotal = row["delivered_total"]
        subtotal_delta = row["comparison"]["reference_minus_delivered_total"]
        asking_delta = row["comparison"]["reference_minus_listing_price"]
        row["comparison"].update(
            reference_minus_listing_and_shipping_subtotal=subtotal_delta,
            reference_minus_delivered_total=None,
            below_reference=Decimal(asking_delta) > 0 if asking_delta is not None else None,
        )
        row.update(
            hunt_status=_status(row),
            observed_at=now.astimezone(UTC).isoformat(),
            minimum_next_bid=_money(raw.get("minimumPriceToBid"))
            if "AUCTION" in row["buying_options"]
            else None,
            buy_now_available="FIXED_PRICE" in row["buying_options"],
            planned_manual_bid=None,
            final_purchase_price=None,
            raw_condition_basis=raw.get("condition") if isinstance(raw.get("condition"), str) else None,
            listing_and_shipping_subtotal=subtotal,
            listing_and_shipping_complete=subtotal is not None,
            delivered_total=None,
            delivered_cost_complete=False,
            tax=None,
            other_costs=None,
            delivered_cost_basis="Listing amount and shipping only; tax and other costs unknown",
            contents_review_required=row["discovery_kind"] == "mixed_lot",
        )
        for identity in [row["proposed_identity"], *row["identity_candidates"]]:
            if identity is not None:
                printing = by_printing[identity["printing_id"]]
                identity["catalog_identity"] = {
                    key: printing.get(key) for key in ("language", "edition", "finish", "variant")
                }
        if row["discovery_kind"] == "unsupported":
            row["label"] = "Unsupported product"
    store.verified(actor)
    if collection.generation(actor) != generation:
        raise collection.Conflict("Catalog changed during Hunter comparison; start a new Hunt")
    return hunter_ranking.project(rows, now=now)


def counts(rows):
    """Sanitized dispositions; every projected summary contributes exactly once."""
    result = dict.fromkeys(STATUSES, 0)
    for row in rows:
        result[row["hunt_status"]] += 1
    return result
