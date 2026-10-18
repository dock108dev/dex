"""Independent, offline complete review of a finite TCGCSV identity crosswalk.

This deliberately does not import the mapping builder or its matching helpers.
It reads the installed catalog without writes and emits identity metadata/counts
only. Prices are inspected in memory for semantics; no amounts or price hashes
are emitted. Admission, snapshot writes and provider operations are unavailable.
"""

import argparse
import hashlib
import json
import re
import socket
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import qualify_hunter

MIB = 1024 * 1024
IDENTITY = ("set_id", "collector_number", "language", "edition", "finish", "variant", "catalog_version")
SUBTYPES = {
    "Normal": ("unspecified", "normal"),
    "Holofoil": ("unspecified", "holo"),
    "Reverse Holofoil": ("unspecified", "reverse-holo"),
    "Unlimited": ("unlimited", "normal"),
    "Unlimited Holofoil": ("unlimited", "holo"),
    "1st Edition": ("first_edition", "normal"),
    "1st Edition Holofoil": ("first_edition", "holo"),
}
FINISHES = {
    "normal": "normal",
    "nonfoil": "normal",
    "holo": "holo",
    "holofoil": "holo",
    "reverse": "reverse-holo",
    "reverse-holo": "reverse-holo",
    "reverse-holofoil": "reverse-holo",
}
EDITIONS = {
    "unlimited": "unlimited",
    "standard": "unlimited",
    "1st-edition": "first_edition",
    "first_edition": "first_edition",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(value, newline=False):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body + (b"\n" if newline else b"")).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def read_json(path, *, prices=False, ceiling=16 * MIB):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink() and path.resolve() == path, "unsafe_input")
    require(path.stat().st_size <= ceiling, "oversized_input")
    with path.open("rb") as stream:
        raw = stream.read(ceiling + 1)
    require(len(raw) <= ceiling, "oversized_input")

    def nonfinite(_):
        raise ValueError("nonfinite_json")

    return json.loads(
        raw,
        object_pairs_hook=unique_object,
        parse_constant=nonfinite,
        **({"parse_float": Decimal} if prices else {}),
    )


def literal(value):
    return " ".join(unicodedata.normalize("NFC", value).replace("’", "'").split())


def token(value):
    value = literal(value).casefold()
    match = re.fullmatch(r"([a-z]*)([0-9]+)([a-z]*)", value)
    return (match[1], int(match[2]), match[3]) if match else value


def collector_matches(local, source, evidence):
    left, right = [p.strip() for p in local.split("/")], [p.strip() for p in source.split("/")]
    if not 1 <= len(left) <= 2 or not 1 <= len(right) <= 2 or token(left[0]) != token(right[0]):
        return False
    if len(left) == len(right) == 2:
        return token(left[1]) == token(right[1])
    if len(left) == len(right) == 1:
        return True
    numerator = re.fullmatch(r"([a-z]*)([0-9]+)([a-z]*)", literal(source.split("/")[0]), re.I)
    if not numerator:
        return False
    allowed = evidence.get("denominators", {}).get(numerator[1].casefold(), [])
    denominator = right[1] if len(right) == 2 else left[1]
    return token(denominator) in {token(value) for value in allowed}


def name_matches(target, source_name, source_number):
    aliases = target.get("attributes", {}).get("name_aliases", [])
    aliases = aliases if isinstance(aliases, list) else []
    genders = {
        "Nidoran♂": "Nidoran M",
        "Nidoran ♂": "Nidoran M",
        "Nidoran♀": "Nidoran F",
        "Nidoran ♀": "Nidoran F",
    }

    def name(value):
        value = literal(value)
        return genders.get(value, value).casefold()

    names = {name(value) for value in [target["name"], *aliases] if isinstance(value, str) and value.strip()}
    value = literal(source_name)
    choices = [value]
    suffixes = [
        re.search(r" \(([^()]*)\)$", value),
        re.search(r" - ([a-z]*[0-9]+[a-z]*(?:/[a-z]*[0-9]+[a-z]*)?)$", value, re.I),
    ]
    for suffix in suffixes:
        if suffix is None:
            continue
        candidate = suffix[1]
        permitted_numbers = {tuple(token(p) for p in source_number.split("/"))}
        if suffix[0].startswith(" ("):
            permitted_numbers.add((token(source_number.split("/")[0]),))
        if (
            re.fullmatch(r"[a-z]*[0-9]+[a-z]*(?:/[a-z]*[0-9]+[a-z]*)?", candidate, re.I)
            and tuple(token(p) for p in candidate.split("/")) in permitted_numbers
        ):
            choices.append(value[: suffix.start()])
    return any(name(choice) in names for choice in choices)


def compatible(target, subtype):
    if subtype not in SUBTYPES or target.get("language") != "en":
        return False
    edition, finish = SUBTYPES[subtype]
    if target.get("edition") and EDITIONS.get(target["edition"]) != edition:
        return False
    if target.get("finish") and FINISHES.get(target["finish"]) != finish:
        return False
    variant = target.get("variant")
    if variant:
        if variant in FINISHES:
            return FINISHES[variant] == finish
        try:
            variant = json.loads(variant)
        except (ValueError, TypeError):
            return False
        if (
            not isinstance(variant, dict)
            or set(variant) - {"type", "stamp"}
            or FINISHES.get(variant.get("type")) != finish
        ):
            return False
        if "stamp" in variant and (variant["stamp"] != ["1st-edition"] or edition != "first_edition"):
            return False
    return True


def source_url_matches(value, product_id):
    if not isinstance(value, str):
        return False
    url = urlsplit(value)
    if (
        url.scheme != "https"
        or url.netloc not in {"www.tcgplayer.com", "tcgplayer.com"}
        or url.query
        or url.fragment
        or not re.match(rf"^/product/{product_id}(?:/|$)", url.path)
    ):
        return False
    slug = url.path.split("/", 3)
    return len(slug) < 4 or not slug[3] or slug[3].startswith("pokemon-")


def product_conflicts(product, target, price_rows=(), subtypes=()):
    conflicts = []
    claims = [product, *price_rows]
    if any("language" in row and row["language"] != "en" for row in claims):
        conflicts.append("language")
    if not source_url_matches(product.get("url"), product["productId"]):
        conflicts.append("url")
    if any(
        row.get(key) is True
        for row in claims
        for key in (
            "isSelectable",
            "isSelectableListing",
            "isSpecial",
            "isSpecialProduct",
            "isSealed",
            "isJumbo",
            "isOversized",
            "isDigital",
            "isGraded",
        )
    ):
        conflicts.append("special_distribution")
    if any(row.get(key) is not None for row in claims for key in ("condition", "grade", "graded")):
        conflicts.append("condition_or_grade")
    if any(
        row.get(key) is not None
        for row in price_rows
        for key in ("as_of", "valuation_date", "publisher_built_at", "reference_as_of", "captured_at")
    ):
        conflicts.append("price_dates")
    if any("currency" in row and row["currency"] != "USD" for row in price_rows):
        conflicts.append("currency")
    for row in claims:
        if row.get("edition") is not None and any(
            EDITIONS.get(row["edition"], row["edition"]) != SUBTYPES[subtype][0] for subtype in subtypes
        ):
            conflicts.append("edition")
        if row.get("finish") is not None and any(
            FINISHES.get(row["finish"], row["finish"]) != SUBTYPES[subtype][1] for subtype in subtypes
        ):
            conflicts.append("finish")
    for field in product["extendedData"]:
        name, value = field["name"].casefold(), field["value"]
        if name == "language" and value.casefold() not in {"en", "english"}:
            conflicts.append("extended_language")
        if name in {"condition", "grade", "graded"} and value.strip():
            conflicts.append("extended_condition_or_grade")
        if name == "supertype" and value.strip():
            category = {"pokemon": "Pokémon", "pokémon": "Pokémon", "trainer": "Trainer", "energy": "Energy"}
            if category.get(value.casefold()) != target.get("attributes", {}).get("supertype"):
                conflicts.append("extended_category")
    return conflicts


def load_sources(directory, group_ids):
    products, prices, cross_products, cross_prices = {}, defaultdict(list), defaultdict(set), defaultdict(set)
    total, row_counts = 0, Counter()
    for gid in group_ids:
        for kind in ("products", "prices"):
            path = directory / "groups" / str(gid) / (kind + ".json")
            total += path.stat().st_size
            require(total <= 64 * MIB, "aggregate_input_limit")
            body = read_json(path, prices=kind == "prices")
            require(
                isinstance(body, dict)
                and body.get("success") is True
                and body.get("errors") == []
                and isinstance(body.get("results"), list),
                "source_envelope",
            )
            require(len(body["results"]) <= 10000, "source_row_limit")
            row_counts[kind] += len(body["results"])
            require(row_counts[kind] <= (100000 if kind == "products" else 200000), "aggregate_row_limit")
            for row in body["results"]:
                require(
                    isinstance(row, dict) and type(row.get("productId")) is int and row["productId"] > 0,
                    "source_product_id",
                )
                pid = row["productId"]
                if kind == "products":
                    require(
                        type(row.get("categoryId")) is int
                        and row["categoryId"] == 3
                        and type(row.get("groupId")) is int
                        and row["groupId"] == gid,
                        "source_category_or_group",
                    )
                    require(
                        isinstance(row.get("name"), str) and isinstance(row.get("extendedData"), list),
                        "source_identity",
                    )
                    require((gid, pid) not in products, "duplicate_product_key")
                    fields = row["extendedData"]
                    require(
                        len(fields) <= 100
                        and all(
                            isinstance(f, dict)
                            and isinstance(f.get("name"), str)
                            and isinstance(f.get("value"), str)
                            for f in fields
                        ),
                        "extended_data_shape",
                    )
                    numbers = [f["value"] for f in fields if f["name"] == "Number"]
                    require(len(numbers) <= 1, "duplicate_collector_number")
                    products[(gid, pid)] = row
                    cross_products[pid].add(gid)
                else:
                    subtype = row.get("subTypeName")
                    require(isinstance(subtype, str) and subtype.strip(), "source_subtype")
                    prices[(gid, pid, subtype)].append(row)
                    cross_prices[(pid, subtype)].add(gid)
    require(all(len(v) == 1 for v in prices.values()), "duplicate_price_key")
    require(all(len(v) == 1 for v in cross_products.values()), "cross_group_product_key")
    require(all(len(v) == 1 for v in cross_prices.values()), "cross_group_price_key")
    return products, prices


def rederive(entries, targets, group_evidence, products, prices, *, exact_bindings=None):
    proposals, counts = {}, Counter()
    for pid, gid in targets.items():
        target = entries[pid]
        exact = exact_bindings[pid] if exact_bindings is not None else None
        options = []
        for (group, product_id), product in products.items():
            if group != gid or exact is not None and product_id != exact["product_id"]:
                continue
            numbers = [f["value"] for f in product["extendedData"] if f["name"] == "Number"]
            if (
                not numbers
                or not collector_matches(target["collector_number"], numbers[0], group_evidence[str(gid)])
                or not name_matches(target, product["name"], numbers[0])
            ):
                continue
            subtypes = [
                sub
                for (g, p, sub) in prices
                if (g, p) == (gid, product_id)
                and compatible(target, sub)
                and (exact is None or sub == exact["sub_type_name"])
            ]
            source_prices = [prices[(gid, product_id, subtype)][0] for subtype in subtypes]
            options.append(
                (product, numbers[0], subtypes, product_conflicts(product, target, source_prices, subtypes))
            )
            if exact is not None and product.get("url") != exact["source_url"]:
                options[-1][3].append("frozen_source_url_conflict")
        if len(options) != 1:
            counts["no_exact_product" if not options else "ambiguous_exact_products"] += 1
            continue
        product, number, subtypes, conflicts = options[0]
        if conflicts or len(subtypes) != 1:
            counts["identity_conflict" if conflicts else "no_unique_compatible_subtype"] += 1
            continue
        proposals[pid] = dict(
            printing_id=pid,
            group_id=gid,
            product_id=product["productId"],
            sub_type_name=subtypes[0],
            product_name=product["name"],
            collector_number=number,
        )
    shared = Counter((b["group_id"], b["product_id"], b["sub_type_name"]) for b in proposals.values())
    for pid, binding in list(proposals.items()):
        if shared[(binding["group_id"], binding["product_id"], binding["sub_type_name"])] != 1:
            del proposals[pid]
            counts["shared_source_key"] += 1
    return proposals, counts


def audit_contract(manifest, entries, proposals, products, built, scope_sha256):
    require(
        set(manifest)
        == {"schema", "publisher_built_at", "captured_at", "expires_at", "contract", "shards", "bindings"}
        and manifest["schema"] == "dex-tcgcsv-offline-v1",
        "manifest_schema",
    )
    require(manifest["publisher_built_at"] == built, "manifest_build")
    captured = datetime.fromisoformat(manifest["captured_at"])
    expires = datetime.fromisoformat(manifest["expires_at"])
    require(
        captured.tzinfo
        and expires.tzinfo
        and datetime.fromisoformat(built) <= captured <= datetime.now(timezone.utc) < expires
        and expires > captured,
        "manifest_dates",
    )
    require(
        sorted(manifest["bindings"], key=lambda b: b["printing_id"])
        == sorted(proposals.values(), key=lambda b: b["printing_id"]),
        "manifest_bindings",
    )
    policy = manifest["contract"]
    require(
        policy.get("schema") == "dex-price-contract-v1" and policy.get("provider") == "TCGCSV",
        "contract_schema",
    )
    require(
        policy.get("copy_policy") == "managed_store_and_permitted_history_no_backups_or_exports",
        "contract_copy_policy",
    )
    require(
        policy.get("rights")
        == dict(
            display=True,
            arithmetic=True,
            private_storage=True,
            immutable_save=False,
            noncontent_revocations=True,
        ),
        "contract_rights",
    )
    require(set(policy.get("fields", {})) == {"marketPrice"}, "contract_fields")
    field = policy["fields"]["marketPrice"]
    require(
        field.get("grade") == "raw"
        and field.get("date_basis") == "publisher_build"
        and field.get("identity_scope") == "conditional_market"
        and field.get("valuation_date_field") is None
        and field.get("reference_date_field") == "last-updated.txt"
        and field.get("unit") == "USD_decimal"
        and field.get("zero_is_value") is False,
        "contract_market_semantics",
    )
    require(set(policy.get("mappings", {})) == set(proposals), "contract_mapping_scope")
    for pid, binding in proposals.items():
        target, mapping = entries[pid], policy["mappings"][pid]
        require(
            set(mapping) == {"identity", "provider_identity", "source_url", "source_version"}, "mapping_shape"
        )
        require(mapping["identity"] == {key: target.get(key) for key in IDENTITY}, "mapping_catalog_identity")
        provider = mapping["provider_identity"]
        require(
            set(provider)
            == {"product_id", "set", "number", "language", "edition", "finish", "variant", "mapping_review"},
            "provider_identity_shape",
        )
        edition, finish = SUBTYPES[binding["sub_type_name"]]
        expected = dict(
            product_id=str(binding["product_id"]),
            set=target["set_name"],
            number=target["collector_number"],
            language="en",
            edition=edition,
            finish=finish,
            variant=binding["sub_type_name"],
        )
        require(
            all(provider[key] == value for key, value in expected.items())
            and isinstance(provider["mapping_review"], str)
            and 0 < len(provider["mapping_review"]) <= 2000,
            "provider_identity_values",
        )
        require(
            provider["mapping_review"].startswith(f"scope:{scope_sha256}; group:{binding['group_id']}; "),
            "mapping_review_scope",
        )
        require(
            mapping["source_url"] == products[(binding["group_id"], binding["product_id"])]["url"]
            and mapping["source_version"] == "tcgcsv-build-" + built,
            "mapping_provenance",
        )
    return digest(policy)


def inspect(root, scope, plan, directory, review, manifest=None):
    entries = qualify_hunter.catalog_metadata(root)
    require(
        digest(entries) == scope.get("catalog_identity_sha256") == review.get("catalog_identity_sha256"),
        "catalog_digest",
    )
    require(scope.get("schema") == "dex-tcgcsv-review-scope-v1", "scope_schema")
    gids = [row["group_id"] for row in plan["groups"]]
    steps = [
        dict(
            filename="build-before.txt", url="https://tcgcsv.com/last-updated.txt", kind="text", group_id=None
        )
    ]
    for gid in gids:
        steps.extend(
            dict(
                filename=f"groups/{gid}/{kind}.json",
                url=f"https://tcgcsv.com/tcgplayer/3/{gid}/{kind}",
                kind=kind,
                group_id=gid,
            )
            for kind in ("products", "prices")
        )
    steps.append(
        dict(
            filename="build-after.txt", url="https://tcgcsv.com/last-updated.txt", kind="text", group_id=None
        )
    )
    require(
        plan.get("root") == str(root)
        and plan.get("purpose") in {"initial_fill", "refresh"}
        and plan.get("include_groups") is False
        and plan.get("steps") == steps
        and plan.get("request_count") == len(steps),
        "finite_plan_scope",
    )
    targets = {
        row["printing_id"]: row["source_group_id"]
        for row in scope["printings"]
        if row["source_group_id"] in gids
    }
    require(
        len(targets) == sum(row["source_group_id"] in gids for row in scope["printings"]),
        "duplicate_scope_target",
    )
    require(set(targets) <= set(entries), "unknown_scope_target")
    exact_bindings = scope.get("exact_bindings")
    if plan["purpose"] == "refresh":
        require(
            scope.get("capture_purpose") == "refresh" and isinstance(exact_bindings, dict),
            "refresh_exact_scope_required",
        )
    if exact_bindings is not None:
        require(set(exact_bindings) == set(targets), "exact_binding_scope")
        for pid, binding in exact_bindings.items():
            require(
                set(binding) == {"group_id", "product_id", "sub_type_name", "source_url"}
                and binding["group_id"] == targets[pid]
                and type(binding["product_id"]) is int
                and binding["sub_type_name"] in SUBTYPES
                and source_url_matches(binding["source_url"], binding["product_id"]),
                "exact_binding_identity",
            )
    evidence = scope["group_evidence"]
    for row in plan["groups"]:
        group = evidence[str(row["group_id"])]
        require(
            group.get("category_id") == 3
            and group.get("literal_name") == row["name"]
            and group.get("language") == "en"
            and bool(group.get("language_evidence"))
            and isinstance(group.get("denominators"), dict),
            "group_evidence",
        )
        if group["denominators"]:
            require(bool(group.get("denominator_evidence")), "missing_denominator_evidence")
    metadata = read_json(directory / "capture-metadata.json")
    require(
        metadata.get("status") == "captured"
        and metadata.get("plan_sha256") == digest(plan, newline=True)
        and metadata.get("group_ids") == gids
        and metadata.get("provider_operations") == 2 * len(gids) + 2,
        "capture_binding",
    )
    require(
        metadata.get("http_statuses") == [200] * len(steps)
        and metadata.get("provider_valuation_at") is None
        and len(metadata.get("files", [])) == len(steps),
        "capture_response_accounting",
    )
    for index, (step, captured_file) in enumerate(zip(steps, metadata["files"], strict=True), 1):
        require(
            captured_file.get("attempt") == index
            and captured_file.get("filename") == step["filename"]
            and captured_file.get("group_id") == step["group_id"]
            and captured_file.get("bytes") == (directory / step["filename"]).stat().st_size,
            "capture_file_accounting",
        )
        captured_time = datetime.fromisoformat(captured_file["captured_at"])
        require(
            captured_time.tzinfo is not None and captured_time <= datetime.now(timezone.utc),
            "capture_future_date",
        )
    before, after = directory / "build-before.txt", directory / "build-after.txt"
    require(before.stat().st_size <= 1024 and before.read_bytes() == after.read_bytes(), "build_conflict")
    built = metadata["publisher_built_at"]
    require(
        datetime.fromisoformat(built).tzinfo is not None
        and datetime.fromisoformat(built) <= datetime.now(timezone.utc),
        "future_or_naive_build",
    )
    require(
        datetime.fromisoformat(before.read_text().strip()).astimezone(timezone.utc).isoformat() == built,
        "publisher_text_metadata_conflict",
    )
    require(review.get("plan_sha256") == digest(plan, newline=True), "review_plan_digest")
    require(review.get("scope_sha256") == digest(scope), "review_scope_digest")
    hash_input = {k: v for k, v in review.items() if k not in {"identity_decisions_sha256", "review_status"}}
    identity_digest = review.get("identity_decisions_sha256")
    # The builder includes review_status in the first decision digest and can
    # subsequently change only that status when writing a reviewed manifest.
    variants = [
        dict(hash_input, review_status=status)
        for status in (
            review.get("review_status"),
            "Independent review required before manifest creation/admission",
        )
    ]
    require(identity_digest in {digest(hash_input), *(digest(v) for v in variants)}, "identity_digest")
    decisions = review["decisions"]
    require(
        len(decisions) == len(targets) and {d["printing_id"] for d in decisions} == set(targets),
        "complete_target_review",
    )
    products, prices = load_sources(directory, gids)
    proposals, exclusions = rederive(
        entries, targets, evidence, products, prices, exact_bindings=exact_bindings
    )
    selected = {}
    for decision in decisions:
        pid = decision["printing_id"]
        require(decision["group_id"] == targets[pid], "review_group_assignment")
        require(
            decision["catalog_identity"]
            == {
                key: entries[pid].get(key)
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
            "review_catalog_identity",
        )
        if decision["selected_binding"]:
            selected[pid] = decision["selected_binding"]
    require(selected == proposals, "independent_mapping_difference")
    if manifest is not None:
        if plan["purpose"] == "refresh":
            require(
                manifest["contract"].get("acquisition_policy")
                == "One finite selected ordinary refresh; no retry, redirect or scheduled acquisition",
                "refresh_contract_purpose",
            )
        require(
            manifest.get("shards")
            == [
                dict(group_id=gid, products=f"groups/{gid}/products.json", prices=f"groups/{gid}/prices.json")
                for gid in gids
            ],
            "manifest_shards",
        )
        require(
            datetime.fromisoformat(manifest["captured_at"])
            == max(datetime.fromisoformat(row["captured_at"]) for row in metadata["files"]),
            "manifest_capture_date",
        )
    contract_digest = (
        audit_contract(manifest, entries, proposals, products, built, digest(scope))
        if manifest is not None
        else None
    )
    return dict(
        schema="dex-tcgcsv-independent-audit-v1",
        all_passed=True,
        all_targets=len(targets),
        selected_bindings=len(proposals),
        excluded_targets=len(targets) - len(proposals),
        independently_rederived_exclusions=dict(exclusions),
        identity_decisions_sha256=identity_digest,
        scope_sha256=digest(scope),
        plan_sha256=digest(plan, newline=True),
        contract_sha256=contract_digest,
        contract_audited=manifest is not None,
        provider_operations=0,
        customer_writes=0,
        imported=False,
        activated=False,
        no_prices_or_price_fingerprints_retained=True,
        independent_of_mapping_builder=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "scope", "plan", "capture-directory", "identity", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    # Defense in depth: even future imported helpers cannot connect.
    def offline(*_args, **_kwargs):
        raise ValueError("offline_audit_forbids_network")

    socket.create_connection = offline
    socket.socket.connect = offline
    try:
        result = inspect(
            args.root,
            read_json(args.scope),
            read_json(args.plan),
            args.capture_directory,
            read_json(args.identity),
            read_json(args.manifest) if args.manifest else None,
        )
        require(not args.output.exists() and not args.output.is_symlink(), "output_exists")
        with args.output.open("x", encoding="utf-8") as stream:
            args.output.chmod(0o600)
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, qualify_hunter.AuditFailure):
        print(
            "Independent offline audit refused; no admission, import or activation attempted.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
