"""Offline exact-identity review of a captured, explicitly frozen TCGCSV batch.

The scope contains reviewed per-printing group assignments and group-specific
catalog evidence. No network, admission, price import or activation occurs here.
Only an exact independently reviewed decision digest unlocks manifest creation.
"""

import argparse
import json
import re
import socket
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import capture_tcgcsv_snapshot as capture  # noqa: E402
import prepare_tcgcsv_offline as preparation  # noqa: E402
import qualify_hunter as audit  # noqa: E402

from pokemon_hunter.beta import discovery_matching, market_identity, tcgcsv_offline  # noqa: E402
from pokemon_hunter.beta import price_snapshot_contract as rules  # noqa: E402

SCOPE_SCHEMA = "dex-tcgcsv-review-scope-v1"


def no_network(*_args, **_kwargs):
    raise ValueError("Offline identity review forbids network access")


def _prefix(number):
    match = re.fullmatch(r"([a-z]*)([0-9]+)([a-z]*)", number, re.I)
    return match[1].casefold() if match else None


def _key(value):
    return str(value).replace(".", "-").casefold()


def build_scope(root, selected_printings, inventory_path, universe_path=None):
    """Freeze reviewed group assignments with retained English catalog evidence.

    ``selected_printings`` are selected rows from S1 printing-review-inventory.
    Ordinary official denominators come from the retained pinned TCGdex universe;
    literal catalog fractions also supply exact prefix-specific denominators.
    An ordinary set total never supplies a prefixed subset's denominator.
    """
    inventory = audit.read_json(Path(inventory_path))
    universe_path = Path(universe_path or REPO / "evidence/d7-20261005/universe.json")
    universe = audit.read_json(universe_path)
    entries = audit.catalog_metadata(Path(root))
    if rules.digest(entries) != inventory["catalog_identity_sha256"]:
        raise ValueError("Current catalog differs from reviewed group inventory")
    rows = []
    selected_by_group = defaultdict(list)
    seen = set()
    for row in selected_printings:
        pid, gid = row["printing_id"], row["source_group_id"]
        if pid in seen or pid not in entries or type(gid) is not int or gid <= 0:
            raise ValueError("Distinct existing printing/group assignments required")
        seen.add(pid)
        rows.append(dict(printing_id=pid, source_group_id=gid))
        selected_by_group[gid].append(entries[pid])
    if not rows:
        raise ValueError("A nonempty frozen target scope is required")
    evidence = {}
    for gid, targets in sorted(selected_by_group.items()):
        set_ids = {target["set_id"] for target in targets}
        sets = [item for item in inventory["set_bindings"] if item["set_id"] in set_ids]
        if len(sets) != len(set_ids):
            raise ValueError("Missing reviewed set crosswalk")
        group_rows, language_records, denominator_records = [], [], []
        denominators = defaultdict(set)
        for item in sets:
            bindings = [group for group in item["source_groups"] if group["group_id"] == gid]
            if len(bindings) != 1 or item["language"] != "en":
                raise ValueError("Missing exact English group crosswalk")
            group = bindings[0]
            if group["category_id"] != 3:
                raise ValueError("Pokemon category evidence required")
            group_rows.append(group)
            external = {
                _key(x["external_id"])
                for x in item["external_set_identity_evidence"]
                if x["provider"] == "tcgdex:en"
            }
            source_sets = [
                source
                for source in universe["sets"]
                if _key(source["provider_set_id"]) in external
                and source["language"] == "en"
                and source["medium"] == "physical"
            ]
            if len(source_sets) != 1:
                raise ValueError("One retained authoritative English set required")
            source = source_sets[0]
            language_records.append(
                dict(
                    set_id=item["set_id"],
                    set_name=item["name"],
                    provider_set_id=source["provider_set_id"],
                    language="en",
                    source_url=source["source_url"],
                    source_sha256=source["source_sha256"],
                    group_selector=group["selector"],
                )
            )
            official = source.get("official_numbered_count")
            # RC, SL, H and other prefix subsets cannot inherit the main total.
            if type(official) is int and official > 0 and group["selector"] != "collector_number_starts_RC":
                denominators[""].add(str(official))
                denominator_records.append(
                    dict(
                        prefix="",
                        denominator=str(official),
                        basis="retained_authoritative_official_numbered_count",
                        source_url=source["source_url"],
                        source_sha256=source["source_sha256"],
                    )
                )
            # Legendary Treasures' reviewed RC-only source group has a separate
            # retained English Radiant Collection set. Its official 25 supports
            # the literal RC25 denominator within the RC numerator scope only;
            # the ordinary Legendary Treasures total 113 supplies no RC evidence.
            if gid == 1465 and group["selector"] == "collector_number_starts_RC" and "bw11" in external:
                supplements = [
                    record
                    for record in universe["sets"]
                    if record.get("id") == "tcgdex:en:rc"
                    and record.get("provider_set_id") == "rc"
                    and record.get("name") == "Radiant Collection"
                    and record.get("language") == "en"
                    and record.get("medium") == "physical"
                    and record.get("release_date") == "2013-11-06"
                    and record.get("official_numbered_count") == 25
                ]
                if len(supplements) != 1:
                    raise ValueError("One retained English Radiant Collection denominator record required")
                supplement = supplements[0]
                denominators["rc"].add("rc25")
                denominator_records.append(
                    dict(
                        prefix="rc",
                        denominator="rc25",
                        official_numbered_count=25,
                        basis="reviewed_RC_only_group_and_retained_Radiant_Collection_official_count",
                        source_url=supplement["source_url"],
                        source_sha256=supplement["source_sha256"],
                    )
                )
                language_records.append(
                    dict(
                        set_id=item["set_id"],
                        set_name=supplement["name"],
                        provider_set_id="rc",
                        language="en",
                        source_url=supplement["source_url"],
                        source_sha256=supplement["source_sha256"],
                        group_selector=group["selector"],
                        supplemental_scope="Legendary Treasures RC-only source group1465; RC-prefix denominator",
                    )
                )
            for target in entries.values():
                if target["set_id"] != item["set_id"]:
                    continue
                is_rc = target["collector_number"].casefold().startswith("rc")
                if (
                    group["selector"] == "collector_number_starts_RC"
                    and not is_rc
                    or group["selector"] == "collector_number_does_not_start_RC"
                    and is_rc
                ):
                    continue
                parts = target["collector_number"].split("/")
                prefix = _prefix(parts[0])
                if len(parts) == 2 and prefix is not None:
                    denominators[prefix].add(parts[1].casefold())
            for target in targets:
                if target["set_id"] != item["set_id"]:
                    continue
                is_rc = target["collector_number"].casefold().startswith("rc")
                if (
                    group["selector"] == "collector_number_starts_RC"
                    and not is_rc
                    or group["selector"] == "collector_number_does_not_start_RC"
                    and is_rc
                ):
                    raise ValueError("Frozen printing violates reviewed subset assignment")
        names = {group["literal_name"] for group in group_rows}
        if len(names) != 1:
            raise ValueError("Conflicting retained source group names")
        evidence[str(gid)] = dict(
            category_id=3,
            literal_name=names.pop(),
            language="en",
            language_evidence=language_records,
            denominators={key: sorted(values) for key, values in sorted(denominators.items())},
            denominator_evidence=denominator_records,
            literal_catalog_fractions_are_evidence=True,
            missing_prefix_denominator_policy="explicit_unresolved_no_main_set_total_substitution",
        )
    return dict(
        schema=SCOPE_SCHEMA,
        catalog_identity_sha256=rules.digest(entries),
        catalog_printings=len(entries),
        printings=sorted(rows, key=lambda row: row["printing_id"]),
        group_evidence=evidence,
        universe_identity_sha256=rules.digest(universe),
    )


def collector_relation(local, source, group_evidence):
    left, right = discovery_matching.number_key(local), discovery_matching.number_key(source)
    if left == right:
        return "literal_equal" if local == source else "padding_normalization"
    if not left or not right or left[0] != right[0] or len(left) > 2 or len(right) > 2:
        return None
    # A known catalog denominator cannot be discarded. If source omits it, the
    # retained authoritative group denominator must independently support it.
    if len(left) == len(right):
        return None
    prefix = _prefix(local.split("/")[0])
    denominator = (source if len(right) == 2 else local).split("/")[1].strip().casefold()
    allowed = group_evidence.get("denominators", {}).get(prefix, [])
    if prefix is None or discovery_matching.number_key(denominator) not in {
        discovery_matching.number_key(token) for token in allowed
    }:
        return None
    return "reviewed_English_set_denominator"


def _alias(value):
    return {
        "Nidoran♂": "Nidoran M",
        "Nidoran ♂": "Nidoran M",
        "Nidoran♀": "Nidoran F",
        "Nidoran ♀": "Nidoran F",
    }.get(value, value)


def product_name_relation(target, source_name, source_number):
    """Preserve literal forms; remove only an agreeing terminal number suffix."""
    value = discovery_matching.literal(source_name)
    choices = [(value, "literal_name")]
    for number in {source_number, source_number.split("/")[0]}:
        suffix = " (" + number + ")"
        if value.endswith(suffix):
            choices.append((value[: -len(suffix)], "literal_name_number_suffix"))
    suffix = re.search(r" \(([a-z]*[0-9]+[a-z]*)\)$", value, re.I)
    if (
        suffix
        and discovery_matching.number_key(suffix[1]) == discovery_matching.number_key(source_number)[0:1]
    ):
        choices.append((value[: suffix.start()], "literal_name_number_suffix_padding_normalization"))
    dash_suffix = re.search(r" - ([a-z]*[0-9]+[a-z]*(?:\s*/\s*[a-z]*[0-9]+[a-z]*)?)$", value, re.I)
    if dash_suffix and discovery_matching.number_key(dash_suffix[1]) == discovery_matching.number_key(
        source_number
    ):
        choices.append(
            (value[: dash_suffix.start()], "literal_name_dash_number_suffix_padding_normalization")
        )
    names = {_alias(discovery_matching.literal(name)).casefold() for name in discovery_matching.names(target)}
    for candidate, reason in choices:
        canonical = _alias(candidate)
        if canonical.casefold() in names:
            alias_used = canonical != candidate or any(
                _alias(name) != name for name in discovery_matching.names(target)
            )
            return reason + ("_retained_Nidoran_gender_alias" if alias_used else "")
    return None


def product_url(value, product_id):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    match = re.fullmatch(r"/product/" + str(product_id) + r"(?:/([^/]+))?/?", parsed.path)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"tcgplayer.com", "www.tcgplayer.com"}
        and parsed.username is None
        and parsed.password is None
        and parsed.port is None
        and match is not None
        and (match[1] is None or match[1].casefold().startswith("pokemon-"))
    )


def _claim_conflicts(product, price_rows, target, subtypes):
    """Literal source claims cannot silently override a conditional reference."""
    result = []
    claims = [product, *price_rows]
    if any("language" in row and row["language"] != "en" for row in claims):
        result.append("known_source_language_conflict")
    if any(
        row.get(key) is True
        for row in claims
        for key in ("isSelectable", "isSelectableListing", "isSpecial", "isSpecialProduct")
    ):
        result.append("selectable_distribution_conflict")
    if any(row.get(key) is not None for row in claims for key in ("condition", "grade", "graded")):
        result.append("unsupported_source_condition_or_grade")
    if any(
        row.get(key) is not None
        for row in price_rows
        for key in ("as_of", "valuation_date", "publisher_built_at", "reference_as_of", "captured_at")
    ):
        result.append("unsupported_price_date_claims")
    if any("currency" in row and row["currency"] != "USD" for row in price_rows):
        result.append("source_currency_conflict")
    for row in claims:
        for key, aliases, index in (
            ("edition", market_identity.EDITION, 0),
            ("finish", market_identity.FINISH, 1),
        ):
            if row.get(key) is not None and any(
                aliases.get(row[key], row[key]) != market_identity.SUBTYPES[subtype][index]
                for subtype in subtypes
            ):
                result.append("source_" + key + "_conflict")
    for field in product["extendedData"]:
        key, value = field["name"].casefold(), field["value"].strip()
        if not value:
            continue
        if key == "language" and value.casefold() not in {"en", "english"}:
            result.append("known_source_language_conflict")
        elif key in {"condition", "grade", "graded"}:
            result.append("unsupported_source_condition_or_grade")
        elif key == "supertype":
            normalized = {
                "pokemon": "Pokémon",
                "pokémon": "Pokémon",
                "trainer": "Trainer",
                "energy": "Energy",
            }
            if normalized.get(value.casefold()) != target.get("attributes", {}).get("supertype"):
                result.append("source_category_conflict")
    return list(dict.fromkeys(result))


def choose(entries, assignments, group_evidence, products, prices, conflicts, *, exact_bindings=None):
    by_group, subtype_keys = defaultdict(list), defaultdict(list)
    for (gid, product_id), rows in products.items():
        if len(rows) != 1 or product_id in conflicts["product_ids"]:
            raise ValueError("Duplicate or cross-group product identity")
        product = rows[0]
        if product.get("categoryId") != 3 or product.get("groupId") != gid:
            raise ValueError("Cross-group or non-Pokemon product identity")
        fields = product["extendedData"]
        if any(
            not isinstance(field, dict)
            or not isinstance(field.get("name"), str)
            or not isinstance(field.get("value"), str)
            for field in fields
        ):
            raise ValueError("Malformed extended identity metadata")
        numbers = [field["value"] for field in fields if field["name"] == "Number"]
        if len(numbers) > 1:
            raise ValueError("Multiple source collector numbers")
        if numbers and numbers[0].strip():
            by_group[gid].append((product, numbers[0]))
    for (gid, (product_id, subtype)), rows in prices.items():
        if len(rows) != 1 or (product_id, subtype) in conflicts["price_keys"]:
            raise ValueError("Duplicate or cross-group subtype identity")
        subtype_keys[(gid, product_id)].append(subtype)
    output = []
    for pid, gid in sorted(assignments.items()):
        target, evidence = entries[pid], group_evidence[str(gid)]
        exact = exact_bindings[pid] if exact_bindings is not None else None
        options, unresolved_numbers = [], 0
        for product, number in by_group[gid]:
            if exact is not None and product["productId"] != exact["product_id"]:
                continue
            name_reason = product_name_relation(target, product["name"], number)
            if not name_reason:
                continue
            number_reason = collector_relation(target["collector_number"], number, evidence)
            if number_reason is None:
                if (
                    discovery_matching.number_key(target["collector_number"])[0]
                    == discovery_matching.number_key(number)[0]
                ):
                    unresolved_numbers += 1
                continue
            allowed = [
                subtype
                for subtype in sorted(subtype_keys[(gid, product["productId"])])
                if subtype in market_identity.SUBTYPES
                and market_identity.compatible(target, *market_identity.SUBTYPES[subtype])
                and (exact is None or subtype == exact["sub_type_name"])
            ]
            price_rows = [prices[(gid, (product["productId"], subtype))][0] for subtype in allowed]
            identity_conflicts = _claim_conflicts(product, price_rows, target, allowed)
            if not product_url(product.get("url"), product["productId"]):
                identity_conflicts.append("invalid_source_identity_url")
            if exact is not None and product.get("url") != exact["source_url"]:
                identity_conflicts.append("frozen_source_url_conflict")
            options.append(
                dict(
                    product_id=product["productId"],
                    product_name=product["name"],
                    collector_number=number,
                    source_url=product.get("url"),
                    source_language=product.get("language"),
                    source_language_unstated="language" not in product,
                    number_relation=number_reason,
                    name_relation=name_reason,
                    supported_subtypes=allowed,
                    identity_conflicts=identity_conflicts,
                )
            )
        supported = any(
            market_identity.compatible(target, *pair) for pair in market_identity.SUBTYPES.values()
        )
        decision = "unsupported_catalog_variant" if not supported else "no_literal_source_product"
        selected = None
        if supported and len(options) > 1:
            decision = "ambiguous_literal_products"
        elif supported and len(options) == 1:
            option = options[0]
            if option["identity_conflicts"]:
                decision = option["identity_conflicts"][0]
            elif not evidence.get("language_evidence") or evidence.get("language") != "en":
                decision = "missing_English_scope_evidence"
            elif not option["supported_subtypes"]:
                decision = "no_supported_literal_subtype"
            elif len(option["supported_subtypes"]) > 1:
                decision = "ambiguous_supported_subtypes"
            else:
                selected = dict(
                    printing_id=pid,
                    group_id=gid,
                    product_id=option["product_id"],
                    sub_type_name=option["supported_subtypes"][0],
                    product_name=option["product_name"],
                    collector_number=option["collector_number"],
                )
                decision = "exact_scoped_binding_proposed_for_independent_review"
        elif supported and unresolved_numbers:
            decision = "collector_denominator_conflict_or_missing_evidence"
        output.append(
            dict(
                printing_id=pid,
                group_id=gid,
                catalog_identity={
                    key: target.get(key)
                    for key in (
                        "set_id",
                        "set_name",
                        "name",
                        "collector_number",
                        "language",
                        "edition",
                        "finish",
                        "variant",
                    )
                },
                decision=decision,
                candidates=options,
                selected_binding=selected,
                unresolved_number_candidates=unresolved_numbers,
            )
        )
    duplicates = Counter(
        (row["group_id"], row["selected_binding"]["product_id"], row["selected_binding"]["sub_type_name"])
        for row in output
        if row["selected_binding"]
    )
    for row in output:
        binding = row["selected_binding"]
        if (
            binding
            and duplicates[(binding["group_id"], binding["product_id"], binding["sub_type_name"])] != 1
        ):
            row.update(decision="shared_source_binding_ambiguous", selected_binding=None)
    return output, [row["selected_binding"] for row in output if row["selected_binding"]]


def contract_for(entries, decisions, bindings, built, review_id, scope):
    """Compact capture-specific contract with the unchanged mixed-condition meaning."""
    policy = dict(
        schema="dex-price-contract-v1",
        provider="TCGCSV",
        review_id=review_id,
        policy_url="https://tcgcsv.com/docs",
        policy_version="reviewed-2026-10-17-owner-corrected-public-snapshots",
        scope="Personal local English ungraded condition-mixed market references; exact reviewed captured product/subtype mappings",
        deletion_policy="Remove at the 30-day reference boundary or withdrawal; no retained price exports",
        acquisition_policy=(
            "One finite selected ordinary refresh; no retry, redirect or scheduled acquisition"
            if scope.get("capture_purpose") == "refresh"
            else "One finite selected initial-fill capture; no retry, redirect or scheduled acquisition"
        ),
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
                currency_evidence="https://tcgcsv.com/docs: United States Dollars",
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
    by_pid = {row["printing_id"]: row for row in decisions}
    scope_digest = rules.digest(scope)
    for binding in bindings:
        pid, subtype = binding["printing_id"], binding["sub_type_name"]
        row, target = by_pid[pid], entries[pid]
        candidate = next(item for item in row["candidates"] if item["product_id"] == binding["product_id"])
        edition, finish = market_identity.SUBTYPES[subtype]
        policy["mappings"][pid] = dict(
            identity={key: target.get(key) for key in rules.IDENTITY},
            provider_identity=dict(
                product_id=str(binding["product_id"]),
                set=target["set_name"],
                number=target["collector_number"],
                language="en",
                edition=edition,
                finish=finish,
                variant=subtype,
                mapping_review=f"scope:{scope_digest}; group:{binding['group_id']}; "
                + candidate["name_relation"]
                + "; "
                + candidate["number_relation"]
                + "; language:"
                + ("unstated;reviewed_English_group" if candidate["source_language_unstated"] else "en")
                + "; conditional mixed-condition reference; no special distribution inferred",
            ),
            source_url=candidate["source_url"],
            source_version="tcgcsv-build-" + built.isoformat(),
        )
    return rules.contract(policy) if bindings else policy


def inspect(root, plan_path, expected_plan, directory, review_id, scope_path):
    started = time.monotonic()
    root, directory = Path(root).absolute(), Path(directory).absolute()
    plan = audit.read_json(Path(plan_path))
    plan_digest = capture.validate_batch_plan(plan, root)
    if (
        plan_digest != expected_plan
        or plan.get("purpose") not in {"initial_fill", "refresh"}
        or plan["include_groups"]
    ):
        raise ValueError("Exact metadata-free selected capture plan required")
    scope = audit.read_json(Path(scope_path))
    entries = audit.catalog_metadata(root)
    if scope.get("schema") != SCOPE_SCHEMA or rules.digest(entries) != scope["catalog_identity_sha256"]:
        raise ValueError("Frozen scope/current catalog conflict")
    exact_bindings = scope.get("exact_bindings")
    if plan["purpose"] == "refresh" and (
        scope.get("capture_purpose") != "refresh" or not isinstance(exact_bindings, dict)
    ):
        raise ValueError("Ordinary refresh requires frozen exact child bindings")
    groups = [group["group_id"] for group in plan["groups"]]
    assignments = {}
    for row in scope["printings"]:
        pid, gid = row["printing_id"], row["source_group_id"]
        if gid in groups:
            if pid in assignments or pid not in entries:
                raise ValueError("Duplicate or missing frozen target")
            assignments[pid] = gid
    if exact_bindings is not None:
        if set(exact_bindings) != set(assignments):
            raise ValueError("Exact binding target scope conflict")
        for pid, binding in exact_bindings.items():
            if (
                set(binding) != {"group_id", "product_id", "sub_type_name", "source_url"}
                or binding["group_id"] != assignments[pid]
                or type(binding["product_id"]) is not int
                or not product_url(binding["source_url"], binding["product_id"])
                or binding["sub_type_name"] not in market_identity.SUBTYPES
            ):
                raise ValueError("Invalid exact source binding")
    for group in plan["groups"]:
        evidence = scope["group_evidence"][str(group["group_id"])]
        if (
            evidence["category_id"] != 3
            or evidence["literal_name"] != group["name"]
            or group["group_id"] not in assignments.values()
        ):
            raise ValueError("Frozen source-group identity conflict")
    metadata = capture._read_private_json(
        preparation._managed_input(root, directory / "capture-metadata.json"),
        plan["limits"]["metadata_bytes"],
    )
    if (
        metadata.get("status") != "captured"
        or metadata.get("plan_sha256") != plan_digest
        or metadata.get("group_ids") != groups
        or metadata.get("provider_operations") != plan["request_count"]
        or metadata.get("capture_directory") != str(directory.relative_to(root))
    ):
        raise ValueError("Exact completed selected capture required")
    before = preparation._managed_input(root, directory / "build-before.txt")
    after = preparation._managed_input(root, directory / "build-after.txt")
    if (
        before.stat().st_size > 1024
        or after.stat().st_size > 1024
        or before.read_bytes() != after.read_bytes()
    ):
        raise ValueError("Publisher build input conflict")
    build = capture._validate(before.read_bytes(), "text")
    if build["publisher_built_at"] != metadata["publisher_built_at"]:
        raise ValueError("Capture build metadata differs")
    shards = [
        dict(group_id=gid, products=f"groups/{gid}/products.json", prices=f"groups/{gid}/prices.json")
        for gid in groups
    ]
    for shard in shards:
        for kind in ("products", "prices"):
            preparation._managed_input(root, directory / shard[kind])
    products, prices, conflicts, totals = tcgcsv_offline._inputs(
        dict(shards=shards), directory, tcgcsv_offline.Limits(), started
    )
    decisions, bindings = choose(
        entries,
        assignments,
        scope["group_evidence"],
        products,
        prices,
        conflicts,
        exact_bindings=exact_bindings,
    )
    built = rules.timestamp(metadata["publisher_built_at"]).astimezone(timezone.utc)
    captured = max(rules.timestamp(row["captured_at"]) for row in metadata["files"])
    now = datetime.now(timezone.utc)
    if built > now or captured > now or built > captured:
        raise ValueError("Future or inconsistent actual build/capture dates")
    policy = contract_for(entries, decisions, bindings, built, review_id, scope)
    expiry = datetime.combine(built.date() + timedelta(days=31), datetime.min.time(), tzinfo=timezone.utc)
    manifest = dict(
        schema=tcgcsv_offline.SCHEMA,
        publisher_built_at=built.isoformat(),
        captured_at=captured.isoformat(),
        expires_at=expiry.isoformat(),
        contract=policy,
        shards=shards,
        bindings=bindings,
    )
    report = dict(
        schema="dex-tcgcsv-complete-identity-decisions-v1",
        plan_sha256=plan_digest,
        scope_sha256=rules.digest(scope),
        catalog_identity_sha256=rules.digest(entries),
        group_ids=groups,
        all_targets=len(decisions),
        proposed_bindings=len(bindings),
        decision_counts=dict(Counter(row["decision"] for row in decisions)),
        source_input_metadata=totals,
        provider_operations=0,
        imported=False,
        activated=False,
        no_prices_price_fingerprints_or_amount_derivatives=True,
        decisions=decisions,
        review_status="Independent review required before manifest creation/admission",
    )
    report["identity_decisions_sha256"] = rules.digest(report)
    if time.monotonic() - started > 30:
        raise ValueError("Existing 30-second preparation ceiling exceeded")
    return report, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "plan", "scope", "capture-directory", "identity-output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--review-id", required=True)
    parser.add_argument("--write-reviewed-manifest", action="store_true")
    parser.add_argument("--reviewed-identity-sha256")
    args = parser.parse_args()
    socket.create_connection = no_network
    socket.socket.connect = no_network
    try:
        if args.identity_output.exists():
            raise ValueError("A new identity metadata output is required")
        report, manifest = inspect(
            args.root,
            args.plan,
            args.expected_plan_sha256,
            args.capture_directory,
            args.review_id,
            args.scope,
        )
        if args.write_reviewed_manifest:
            if (
                args.reviewed_identity_sha256 != report["identity_decisions_sha256"]
                or not manifest["bindings"]
            ):
                raise ValueError("Independent exact complete decision digest and nonempty bindings required")
            manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
            plan = audit.read_json(args.plan)
            ceiling = plan["limits"]["staging_bytes"]
            if (
                len(manifest_bytes) > rules.MAX_BYTES
                or capture._staging_size(args.root / "price-snapshots/staging", ceiling) + len(manifest_bytes)
                > ceiling
            ):
                raise ValueError("Manifest exceeds existing output/staging ceiling")
            capture._write_new(args.capture_directory / "reviewed-manifest.json", manifest_bytes)
            report["review_status"] = (
                "Exact independent decision digest supplied; source admission remains separate"
            )
        report_bytes = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
        if len(report_bytes) > rules.MAX_BYTES:
            raise ValueError("Identity output exceeds existing 16 MiB ceiling")
        capture._write_new(args.identity_output, report_bytes)
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "all_targets",
                        "proposed_bindings",
                        "decision_counts",
                        "identity_decisions_sha256",
                    )
                }
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TypeError, audit.AuditFailure, capture.CaptureRefused):
        print("Offline identity review refused; no admission/import/activation attempted.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
