"""Bounded preparation of retained TCGCSV files; no acquisition or admission.

The caller supplies every product/subtype binding and an independently reviewed
contract. This module neither discovers a plausible printing nor grants rights.
Its output is an ordinary v2 snapshot for the existing lifecycle, never a store.
"""

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from . import price_snapshot_contract as rules

SCHEMA = "dex-tcgcsv-offline-v1"


@dataclass(frozen=True)
class Limits:
    """Engineering ceilings, not provider acquisition authority or allowances."""

    groups: int = 68
    file_bytes: int = rules.MAX_BYTES
    total_bytes: int = 64 * 1024 * 1024
    rows_per_file: int = 10000
    product_rows: int = 100000
    price_rows: int = 200000
    bindings: int = rules.MAX_ROWS
    output_bytes: int = rules.MAX_BYTES
    duration_seconds: float = 30


def _limits(value):
    result = value or Limits()
    if not isinstance(result, Limits) or any(
        type(v) is not int or v <= 0 for k, v in vars(result).items() if k != "duration_seconds"
    ):
        raise ValueError("Positive finite offline limits required")
    if (
        type(result.duration_seconds) not in (int, float)
        or not 0 < result.duration_seconds <= 30
        or result.groups > 68
        or result.file_bytes > rules.MAX_BYTES
        or result.total_bytes > 64 * 1024 * 1024
        or result.rows_per_file > 10000
        or result.product_rows > 100000
        or result.price_rows > 200000
        or result.bindings > rules.MAX_ROWS
        or result.output_bytes > rules.MAX_BYTES
    ):
        raise ValueError("Offline limits cannot exceed the qualified ceilings")
    return result


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON object key")
        value[key] = item
    return value


def _invalid_number(_):
    raise ValueError("Nonfinite JSON number")


def _read(path, maximum):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("Offline input missing, linked or over the byte ceiling")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Offline input exceeds the byte ceiling")
    try:
        value = json.loads(
            raw,
            parse_float=Decimal,
            parse_constant=_invalid_number,
            object_pairs_hook=_unique_object,
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Malformed, duplicate-key or truncated offline JSON") from exc
    return value, len(raw)


def read_manifest(path, *, limits=None):
    """Read a finite local manifest, without writing or reading managed prices."""
    value, _ = _read(path, _limits(limits).file_bytes)
    if not isinstance(value, dict):
        raise ValueError("Offline manifest must be a JSON object")
    return value


def _local_path(directory, value):
    if not isinstance(value, str) or not value or len(value) > 500:
        raise ValueError("Explicit relative offline file required")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("Offline files must remain inside the input directory")
    root = Path(directory).resolve(strict=True)
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Offline input links are unsupported")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Offline files must remain inside the input directory")
    return path


def _positive_id(value):
    return type(value) is int and 0 < value <= 2147483647


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 2000


def _deadline(start, limits):
    if time.monotonic() - start > limits.duration_seconds:
        raise ValueError("Offline preparation exceeded its duration ceiling")


def _envelope(value, kind, limits):
    required = {"success", "errors", "results"}
    if kind == "products":
        required.add("totalItems")
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("success") is not True
        or value.get("errors") != []
        or not isinstance(value.get("results"), list)
        or len(value["results"]) > limits.rows_per_file
    ):
        raise ValueError("Invalid, failed or oversized TCGCSV " + kind + " envelope")
    if kind == "products" and (
        type(value["totalItems"]) is not int or value["totalItems"] != len(value["results"])
    ):
        raise ValueError("Truncated or inconsistent product row count")
    return value["results"]


def _inputs(manifest, directory, limits, start):
    shards = manifest["shards"]
    if not isinstance(shards, list) or not 1 <= len(shards) <= limits.groups:
        raise ValueError("One to 68 explicit input groups required")
    products, prices = defaultdict(list), defaultdict(list)
    product_groups, price_groups = defaultdict(set), defaultdict(set)
    seen_groups, seen_files = set(), set()
    byte_count, row_count = 0, Counter()
    for shard in shards:
        _deadline(start, limits)
        if (
            not isinstance(shard, dict)
            or set(shard) != {"group_id", "products", "prices"}
            or not _positive_id(shard.get("group_id"))
            or shard["group_id"] in seen_groups
        ):
            raise ValueError("Distinct explicit group shard identities required")
        group = shard["group_id"]
        seen_groups.add(group)
        for kind, target in (("products", products), ("prices", prices)):
            path = _local_path(directory, shard[kind])
            if path in seen_files:
                raise ValueError("An input file cannot be reused across group shards")
            seen_files.add(path)
            value, size = _read(path, min(limits.file_bytes, limits.total_bytes - byte_count))
            byte_count += size
            if byte_count > limits.total_bytes:
                raise ValueError("Offline input exceeds total byte ceiling")
            rows = _envelope(value, kind, limits)
            row_count[kind] += len(rows)
            if row_count[kind] > getattr(limits, "product_rows" if kind == "products" else "price_rows"):
                raise ValueError("Offline input exceeds total row ceiling")
            for row in rows:
                _deadline(start, limits)
                if not isinstance(row, dict) or not _positive_id(row.get("productId")):
                    raise ValueError("Malformed TCGCSV product identity")
                if kind == "products":
                    if (
                        row.get("categoryId") != 3
                        or type(row.get("categoryId")) is not int
                        or row.get("groupId") != group
                        or type(row.get("groupId")) is not int
                        or not _text(row.get("name"))
                        or not isinstance(row.get("extendedData"), list)
                        or len(row["extendedData"]) > 100
                    ):
                        raise ValueError("Malformed or cross-group TCGCSV product")
                    key = row["productId"]
                else:
                    if not _text(row.get("subTypeName")):
                        raise ValueError("Missing literal TCGCSV subtype")
                    key = (row["productId"], row["subTypeName"])
                target[(group, key)].append(row)
                (product_groups if kind == "products" else price_groups)[key].add(group)
    _deadline(start, limits)
    conflicts = dict(
        product_ids={key for key, groups in product_groups.items() if len(groups) > 1},
        price_keys={key for key, groups in price_groups.items() if len(groups) > 1},
    )
    return (
        products,
        prices,
        conflicts,
        dict(
            groups=len(shards),
            files=len(seen_files),
            input_bytes=byte_count,
            product_rows=row_count["products"],
            price_rows=row_count["prices"],
        ),
    )


def _binding_rows(bindings, limits):
    if not isinstance(bindings, list) or len(bindings) > limits.bindings:
        raise ValueError("Explicit finite reviewed binding list required")
    by_printing, by_source = defaultdict(list), defaultdict(list)
    keys = {"printing_id", "group_id", "product_id", "sub_type_name", "product_name", "collector_number"}
    for item in bindings:
        if (
            not isinstance(item, dict)
            or set(item) != keys
            or not _positive_id(item.get("group_id"))
            or not _positive_id(item.get("product_id"))
            or any(
                not _text(item.get(k))
                for k in ("printing_id", "sub_type_name", "product_name", "collector_number")
            )
        ):
            raise ValueError("Malformed explicit product/subtype binding")
        by_printing[item["printing_id"]].append(item)
        by_source[(item["group_id"], item["product_id"], item["sub_type_name"])].append(item)
    return by_printing, by_source


def _decision(printing, binding, policy, products, prices, by_source, built, conflicts):
    """Return an explicit rejection or the sole reviewed record inputs."""
    pid, gid, product_id = printing["id"], binding["group_id"], binding["product_id"]
    subtype = binding["sub_type_name"]
    if len(by_source[(gid, product_id, subtype)]) != 1:
        return "ambiguous_source_binding", None
    if product_id in conflicts["product_ids"] or (product_id, subtype) in conflicts["price_keys"]:
        return "cross_group_identity_conflict", None
    mapping = policy["mappings"].get(pid)
    if not isinstance(mapping, dict) or set(mapping) != {
        "identity",
        "provider_identity",
        "source_url",
        "source_version",
    }:
        return "missing_reviewed_mapping", None
    provider = mapping["provider_identity"]
    if not isinstance(provider, dict) or set(provider) != {
        "product_id",
        "set",
        "number",
        "language",
        "edition",
        "finish",
        "variant",
        "mapping_review",
    }:
        return "invalid_reviewed_mapping", None
    if any(not _text(value) for value in provider.values()):
        return "invalid_reviewed_mapping", None
    if mapping["identity"] != {k: printing.get(k) for k in rules.IDENTITY}:
        return "catalog_identity_conflict", None
    if (
        provider["product_id"] != str(product_id)
        or provider["set"] != printing["set_name"]
        or provider["number"] != printing["collector_number"]
        or provider["variant"] != subtype
        or mapping["source_version"] != "tcgcsv-build-" + built.isoformat()
    ):
        return "reviewed_source_identity_conflict", None
    if provider["language"] != "en" or printing.get("language") != "en":
        return "language_conflict", None
    candidates = products.get((gid, product_id), [])
    if len(candidates) != 1:
        return ("ambiguous_product" if candidates else "unmapped_product"), None
    product = candidates[0]
    if product["name"] != binding["product_name"] or product.get("url") != mapping["source_url"]:
        return "product_identity_conflict", None
    numbers = []
    for field in product["extendedData"]:
        if (
            not isinstance(field, dict)
            or not _text(field.get("name"))
            or not isinstance(field.get("value"), str)
        ):
            return "malformed_extended_data", None
        if field["name"] == "Number":
            numbers.append(field["value"])
    if len(numbers) != 1 or numbers[0] != binding["collector_number"]:
        return "collector_number_conflict", None
    for metadata in (product,):
        if "language" in metadata and metadata["language"] != provider["language"]:
            return "language_conflict", None
    candidates = prices.get((gid, (product_id, subtype)), [])
    if len(candidates) != 1:
        return ("ambiguous_price" if candidates else "unmapped_price"), None
    source = candidates[0]
    if "currency" in source and source["currency"] != "USD":
        return "currency_conflict", None
    # The documented source provides no condition-specific or valuation-date
    # column. Extra claims cannot silently override that reviewed meaning.
    if any(source.get(k) is not None for k in ("as_of", "valuation_date", "condition", "grade", "graded")):
        return "unsupported_price_semantics", None
    if any(source.get(k) is not None for k in ("publisher_built_at", "reference_as_of", "captured_at")):
        return "conflicting_price_dates", None
    if "language" in source and source["language"] != provider["language"]:
        return "language_conflict", None
    value = source.get("marketPrice")
    if value is None:
        return "missing_market_price", None
    if type(value) is int:
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        return "invalid_market_price", None
    if (
        value > rules.shopping_math.CAP
        or not -6 <= value.as_tuple().exponent <= 12
        or len(value.as_tuple().digits) > 19
    ):
        return "invalid_market_price", None
    money = format(value, "f")
    try:
        rules.shopping_math.amount(money)
    except ValueError:
        return "invalid_market_price", None
    return "prepared", dict(mapping=mapping, money=money)


def prepare(
    entries, manifest, *, input_directory, now=None, baseline_eligible=(), limits=None, target_ids=None
):
    """Prepare an all-or-nothing finite release and metadata-only dry-run report.

    No state is changed. The supplied contract is preserved byte-semantically;
    activation still requires the ordinary independent admission registry. Any
    malformed/partial shard aborts preparation before a package is returned.
    A zero-record projection returns ``None`` plus its rejection report.
    """
    start, limits = time.monotonic(), _limits(limits)
    now = now or datetime.now(timezone.utc)
    if (
        not isinstance(manifest, dict)
        or set(manifest)
        != {"schema", "publisher_built_at", "captured_at", "expires_at", "contract", "shards", "bindings"}
        or manifest.get("schema") != SCHEMA
    ):
        raise ValueError("Unsupported offline manifest structure")
    if not isinstance(entries, dict) or len(entries) > rules.MAX_CATALOG_ROWS:
        raise ValueError("Current catalog exceeds the finite lookup ceiling")
    if rules.serialized_bytes(entries) > rules.MAX_CATALOG_BYTES:
        raise ValueError("Current catalog exceeds the finite lookup byte ceiling")
    if any(not isinstance(p, dict) or p.get("id") != key for key, p in entries.items()):
        raise ValueError("Explicit canonical catalog identities required")
    built = rules.timestamp(manifest["publisher_built_at"]).astimezone(timezone.utc)
    captured = rules.timestamp(manifest["captured_at"]).astimezone(timezone.utc)
    if now.tzinfo is None or built > captured or captured > now:
        raise ValueError("Publisher build, capture and current time conflict")
    expiry = rules.timestamp(manifest["expires_at"])
    if expiry <= now or expiry <= captured:
        raise ValueError("A future removable source expiry is required")
    policy = rules.contract(manifest["contract"])
    if policy["provider"] != "TCGCSV" or set(policy["fields"]) != {"marketPrice"}:
        raise ValueError("This adapter accepts only a supplied TCGCSV raw marketPrice contract")
    field = policy["fields"]["marketPrice"]
    if (
        field.get("grade") != "raw"
        or field.get("date_basis") != "publisher_build"
        or field.get("identity_scope") != "conditional_market"
    ):
        raise ValueError("TCGCSV condition-mixed publisher-build meaning must remain explicit")
    by_printing, by_source = _binding_rows(manifest["bindings"], limits)
    # Lookup/coverage denominator and selected import targets are independent.
    # Unbound catalog entries stay visible in the audit, without spending a slot.
    targets = set(by_printing) if target_ids is None else target_ids
    if (
        not isinstance(targets, (set, list, tuple))
        or len(targets) > limits.bindings
        or any(not isinstance(pid, str) for pid in targets)
        or len(set(targets)) != len(targets)
    ):
        raise ValueError("Finite distinct explicit import targets required")
    targets = set(targets)
    if not set(by_printing) <= targets:
        raise ValueError("A supplied binding lies outside the selected import targets")
    products, prices, conflicts, totals = _inputs(manifest, input_directory, limits, start)
    rows, decisions = [], []
    for pid, printing in sorted(entries.items()):
        _deadline(start, limits)
        bindings = by_printing.get(pid, [])
        prepared = None
        if pid not in targets or not bindings:
            decision = "unmapped_printing"
        elif len(bindings) != 1:
            decision = "ambiguous_printing_binding"
        else:
            decision, prepared = _decision(
                printing, bindings[0], policy, products, prices, by_source, built, conflicts
            )
        if prepared is not None:
            row = dict(
                observation_id=str(uuid4()),
                printing_id=pid,
                **prepared["mapping"],
                field="marketPrice",
                grade="raw",
                grader=field["grader"],
                original_money=prepared["money"],
                value=prepared["money"],
                currency="USD",
                as_of=None,
                reference_as_of=built.date().isoformat(),
                publisher_built_at=built.isoformat(),
                captured_at=captured.isoformat(),
                estimated=True,
                estimate_kind="provider_guide",
                match_scope="conditional_market",
            )
            decision = rules.reason(row, printing, now.date())
            if decision in {"eligible", "stale"}:
                rows.append(row)
        decisions.append(dict(printing_id=pid, decision=decision))
    absent_bindings = [
        dict(printing_id=pid, decision="printing_absent_from_catalog")
        for pid in sorted(set(by_printing) - set(entries))
    ]
    package = None
    if rows:
        review_id = policy["review_id"]
        package = dict(
            schema="dex-price-snapshot-v2",
            version=str(uuid4()),
            release_month=captured.strftime("%Y-%m"),
            contracts={review_id: dict(contract=policy, expires_at=manifest["expires_at"])},
            records=[dict(row, contract_id=review_id) for row in rows],
        )
        rules.validate(package, entries, now=now)
        if len(json.dumps(package, separators=(",", ":")).encode()) > limits.output_bytes:
            raise ValueError("Prepared release exceeds the existing snapshot byte ceiling")
    baseline = set(baseline_eligible)
    if not baseline <= set(entries):
        raise ValueError("Baseline eligible identities must belong to the exact current catalog")
    eligible = {d["printing_id"] for d in decisions if d["decision"] == "eligible"}
    source_keys = {(gid, key[0], key[1]) for gid, key in prices}
    unmapped = source_keys - set(by_source)
    report = dict(
        schema="dex-tcgcsv-offline-report-v1",
        evidence="offline_projection_not_acquired_coverage",
        catalog_printings=len(entries),
        selected_target_printings=len(targets),
        selected_catalog_printings=len(targets & set(entries)),
        records=len(rows),
        eligible_printings=len(eligible),
        baseline_eligible_printings=len(baseline),
        projected_eligible_printings=len(baseline | eligible),
        newly_eligible_printings=len(eligible - baseline),
        projected_unpriced_printings=len(set(entries) - (baseline | eligible)),
        decisions=dict(Counter(d["decision"] for d in decisions)),
        printings=decisions,
        bindings_absent_from_catalog=len(absent_bindings),
        unpublished_bindings=absent_bindings,
        unmapped_source_rows=sum(len(prices[(g, (p, s))]) for g, p, s in unmapped),
        ambiguous_source_keys=sum(len(v) > 1 for v in prices.values()),
        duplicate_product_keys=sum(len(v) > 1 for v in products.values()),
        cross_group_product_ids=len(conflicts["product_ids"]),
        cross_group_price_keys=len(conflicts["price_keys"]),
        publisher_built_at=built.isoformat(),
        provider_valuation_date=None,
        captured_at=captured.isoformat(),
        contract_sha256=rules.digest(policy),
        input=totals,
        activation="not_performed_independent_admission_required",
    )
    _deadline(start, limits)
    return package, report
