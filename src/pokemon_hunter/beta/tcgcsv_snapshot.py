"""Build a private raw snapshot from one retained TCGCSV export, without network I/O."""

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from . import price_snapshot_contract as rules
from .market_identity import SUBTYPES, compatible

GROUPS = {
    "Base Set": 604,
    "Jungle": 635,
    "Fossil": 630,
    "Base Set 2": 605,
    "Team Rocket": 1373,
    "Gym Heroes": 1441,
    "Gym Challenge": 1440,
    "Neo Genesis": 1396,
    "Neo Discovery": 1434,
    "Neo Revelation": 1389,
    "Neo Destiny": 1444,
}


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:/[0-9]+)?", value):
        return None
    return str(int(value.split("/")[0]))


def name(value, card_number):
    # A documented product name may append its disambiguating card number.
    # Do not conflate editions, promo names or broadly strip punctuation.
    suffix = " (" + card_number + ")"
    if value.endswith(suffix):
        value = value[: -len(suffix)]
    for old, new in (
        ("Nidoran♂", "Nidoran M"),
        ("Nidoran♀", "Nidoran F"),
        ("Nidoran ♂", "Nidoran M"),
        ("Nidoran ♀", "Nidoran F"),
    ):
        value = value.replace(old, new)
    return value.replace("’", "'").casefold()


def build(entries, products, prices, *, built_at, captured_at):
    built = rules.timestamp(built_at).astimezone(timezone.utc)
    captured = rules.timestamp(captured_at)
    if built > captured or built.strftime("%Y-%m") != "2026-10":
        raise ValueError("This release requires an observed October 2026 publisher build")
    policy = dict(
        schema="dex-price-contract-v1",
        provider="TCGCSV",
        review_id="tcgcsv-oct2026-raw-v1",
        policy_url="https://tcgcsv.com/docs",
        policy_version="reviewed-2026-10-10",
        scope="Personal local ungraded market references across conditions, eleven vintage sets",
        deletion_policy="Remove at the 30-day reference boundary or source withdrawal; no retained price exports",
        acquisition_policy="One paced daily export sync; custom User-Agent; no account or payment",
        copy_policy="managed_store_and_permitted_history_no_backups_or_exports",
        rights=dict(
            display=True,
            arithmetic=True,
            private_storage=True,
            immutable_save=False,
            noncontent_revocations=True,
        ),
        fields={
            "marketPrice": dict(
                grade="raw",
                grader="TCGplayer ungraded market",
                label="Ungraded market reference across conditions",
                currency_evidence="https://tcgcsv.com/docs states prices are United States Dollars",
                valuation_date_field=None,
                reference_date_field="last-updated.txt",
                date_basis="publisher_build",
                identity_scope="conditional_market",
                unit="USD_decimal",
                zero_is_value=False,
            )
        },
        mappings={},
    )
    records, decisions = [], []
    for p in entries.values():
        attributes = p["attributes"]
        species = attributes.get("pokemon_dex")
        if p["set_name"] not in GROUPS or type(species) is not int or not 1 <= species <= 151:
            continue
        reason, candidates = "no_unique_product", []
        gid = GROUPS[p["set_name"]]
        wanted = number(p["collector_number"])
        for product in products[gid]:
            ext = {f["name"]: f["value"] for f in product.get("extendedData", [])}
            if (
                product.get("categoryId") == 3
                and product.get("groupId") == gid
                and number(ext.get("Number")) == wanted
                and wanted is not None
                and name(product["name"], wanted) == name(p["name"], wanted)
            ):
                candidates.append(product)
        if len(candidates) == 1:
            product = candidates[0]
            rows = [
                r
                for r in prices[gid]
                if r.get("productId") == product["productId"] and r.get("subTypeName") in SUBTYPES
            ]
            rows = [r for r in rows if compatible(p, *SUBTYPES[r["subTypeName"]])]
            # Unknown catalog edition uses the explicitly labelled Unlimited reference
            # where available, without writing that edition to collection metadata.
            if not p.get("edition") and any(SUBTYPES[r["subTypeName"]][0] == "unlimited" for r in rows):
                rows = [r for r in rows if SUBTYPES[r["subTypeName"]][0] == "unlimited"]
            reason = "conflicting_or_ambiguous_subtype"
            if len(rows) == 1:
                source = rows[0]
                value = source.get("marketPrice")
                reason = "missing_or_zero_market_price"
                if type(value) is int:
                    value = Decimal(value)
                if isinstance(value, Decimal) and value.is_finite() and value > 0:
                    money = format(value, "f")
                    rules.shopping_math.amount(money)
                    subtype = source["subTypeName"]
                    edition, finish = SUBTYPES[subtype]
                    provider = dict(
                        product_id=str(product["productId"]),
                        set=p["set_name"],
                        number=p["collector_number"],
                        language="en",
                        edition=edition,
                        finish=finish,
                        variant=subtype,
                        mapping_review="Observed English group, exact card name/number, literal productId/subTypeName; conditional physical fit",
                    )
                    mapping = dict(
                        identity={k: p.get(k) for k in rules.IDENTITY},
                        provider_identity=provider,
                        source_url=product["url"],
                        source_version="tcgcsv-build-" + built.isoformat(),
                    )
                    policy["mappings"][p["id"]] = mapping
                    records.append(
                        dict(
                            observation_id=str(uuid4()),
                            printing_id=p["id"],
                            **mapping,
                            field="marketPrice",
                            grade="raw",
                            grader="TCGplayer ungraded market",
                            original_money=money,
                            value=money,
                            currency="USD",
                            as_of=None,
                            reference_as_of=built.date().isoformat(),
                            publisher_built_at=built.isoformat(),
                            captured_at=captured.isoformat(),
                            estimated=True,
                            estimate_kind="provider_guide",
                            match_scope="conditional_market",
                        )
                    )
                    reason = "conditional_market_reference"
        decisions.append(
            dict(
                printing_id=p["id"],
                set=p["set_name"],
                number=p["collector_number"],
                name=p["name"],
                decision=reason,
            )
        )
    expiry = datetime.combine(built.date() + timedelta(days=31), datetime.min.time(), tzinfo=timezone.utc)
    package = dict(
        schema="dex-price-snapshot-v1",
        version=str(uuid4()),
        release_month="2026-10",
        contract=policy,
        expires_at=expiry.isoformat(),
        records=records,
    )
    if not records:
        raise ValueError("Snapshot needs a nonempty supported record set")
    rules.validate(package, entries, now=captured)
    return package, dict(
        priority_printings=len(decisions),
        records=len(records),
        decisions=dict(Counter(d["decision"] for d in decisions)),
        printings=decisions,
        publisher_built_at=built.isoformat(),
        provider_valuation_date=None,
    )
