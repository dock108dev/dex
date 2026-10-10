"""Offline price package semantics. A declared contract is not provider permission."""

import hashlib
import json
import re
import uuid
from datetime import date, datetime, timezone

from pokemon_hunter import reference_policy as references

from . import shopping_math

COLUMNS = ("raw", "8", "9", "10")
IDENTITY = ("set_id", "collector_number", "language", "edition", "finish", "variant", "catalog_version")
MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 10000


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("A timezone-aware timestamp is required")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("A timezone-aware timestamp is required")
    return result


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ValueError("Missing source contract evidence")
    return value


def contract(value):
    if not isinstance(value, dict) or value.get("schema") != "dex-price-contract-v1":
        raise ValueError("Unsupported price contract")
    for key in ("provider", "review_id", "policy_version", "scope", "deletion_policy", "acquisition_policy"):
        text(value.get(key))
    if not references.source_url(value.get("policy_url")):
        raise ValueError("Missing applicable source policy URL")
    rights = value.get("rights")
    if not isinstance(rights, dict) or set(rights) != {
        "display",
        "arithmetic",
        "private_storage",
        "immutable_save",
        "noncontent_revocations",
    }:
        raise ValueError("Explicit independent source rights required")
    if any(type(v) is not bool for v in rights.values()) or not all(
        rights[k] for k in ("display", "arithmetic", "private_storage", "noncontent_revocations")
    ):
        raise ValueError("Source display, arithmetic, storage and revocation rights unavailable")
    # This implementation manages one private store, no price backups or exports.
    # Broader copy/deletion obligations require additional engineering before admission.
    if value.get("copy_policy") != "managed_store_and_permitted_history_no_backups_or_exports":
        raise ValueError("Unsupported copy/deletion reach")
    fields = value.get("fields")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("Literal provider fields required")
    for key, field in fields.items():
        text(key)
        if not isinstance(field, dict) or field.get("grade") not in COLUMNS:
            raise ValueError("Unsupported exact grade; bands cannot substitute for Grade 8")
        for k in ("label", "grader", "currency_evidence"):
            text(field.get(k))
        date_basis = field.get("date_basis", "valuation")
        if "identity_scope" in field and not (
            field["identity_scope"] == "conditional_market"
            and value["provider"] == "TCGCSV"
            and key == "marketPrice"
            and field["grade"] == "raw"
            and date_basis == "publisher_build"
        ):
            raise ValueError("Conditional market scope is supported only for TCGCSV raw marketPrice")
        if date_basis == "publisher_build":
            if value["provider"] != "TCGCSV" or field["grade"] != "raw":
                raise ValueError("Publisher build references are approved only for TCGCSV ungraded")
            if (
                field.get("valuation_date_field") is not None
                or field.get("reference_date_field") != "last-updated.txt"
            ):
                raise ValueError("TCGCSV build and unavailable valuation dates must remain explicit")
        elif date_basis == "valuation":
            text(field.get("valuation_date_field"))
        else:
            raise ValueError("Unsupported source date basis")
        if field.get("unit") != "USD_decimal" or type(field.get("zero_is_value")) is not bool:
            raise ValueError("Original decimal USD unit and zero meaning required")
    mappings = value.get("mappings")
    if not isinstance(mappings, dict) or not mappings:
        raise ValueError("Independently reviewed exact provider mappings required")
    return value


def validate(package, entries, *, now=None):
    now = now or datetime.now(timezone.utc)
    if isinstance(package, dict) and package.get("schema") == "dex-price-snapshot-v2":
        return validate_sources(package, entries, now=now)
    if (
        not isinstance(package, dict)
        or set(package) != {"schema", "version", "release_month", "contract", "expires_at", "records"}
        or package.get("schema") != "dex-price-snapshot-v1"
    ):
        raise ValueError("Unsupported price snapshot structure")
    version = package["version"]
    if not isinstance(version, str) or str(uuid.UUID(version)) != version:
        raise ValueError("Snapshot version must be a canonical UUID")
    if not isinstance(package["release_month"], str) or not re.fullmatch(
        r"\d{4}-\d{2}", package["release_month"]
    ):
        raise ValueError("Snapshot release month required")
    date.fromisoformat(package["release_month"] + "-01")
    policy = contract(package["contract"])
    if package["expires_at"] is not None:
        if timestamp(package["expires_at"]) <= now:
            raise ValueError("Snapshot expired; restore excluded")
    elif not policy["rights"]["immutable_save"]:
        raise ValueError("Removable snapshots require an explicit expiry")
    records = package["records"]
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_ROWS:
        raise ValueError("Snapshot needs a finite, nonempty record set")
    ids, cells = set(), set()
    for row in records:
        field = None
        if isinstance(row, dict):
            field = policy["fields"].get(row.get("field"))
        build_reference = bool(field and field.get("date_basis") == "publisher_build")
        fields = {
            "observation_id",
            "printing_id",
            "identity",
            "provider_identity",
            "field",
            "grade",
            "grader",
            "original_money",
            "value",
            "currency",
            "as_of",
            "captured_at",
            "estimated",
            "estimate_kind",
            "source_url",
            "source_version",
        }
        if build_reference:
            fields |= {"reference_as_of", "publisher_built_at"}
        if field and field.get("identity_scope") == "conditional_market":
            fields.add("match_scope")
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Unsupported observation structure")
        if "match_scope" in row and row["match_scope"] != "conditional_market":
            raise ValueError("Unsupported market identity scope")
        oid = text(row["observation_id"])
        if oid in ids:
            raise ValueError("Duplicate observation identity")
        ids.add(oid)
        mapping = policy["mappings"].get(row["printing_id"])
        if not mapping or mapping != {
            k: row[k] for k in ("identity", "provider_identity", "source_url", "source_version")
        }:
            raise ValueError("Observation differs from independently reviewed source mapping")
        field = policy["fields"].get(row["field"])
        if not field or (row["grade"], row["grader"]) != (field["grade"], field["grader"]):
            raise ValueError("Literal field/grade/grader conflict")
        key = (row["printing_id"], row["grade"], reference_date(row))
        if key in cells:
            raise ValueError("Conflicting or duplicate dated cell")
        cells.add(key)
        if row["printing_id"] not in entries:
            raise ValueError("Printing is absent from the installed selectable catalog")
        if not isinstance(row["identity"], dict) or set(row["identity"]) != set(IDENTITY):
            raise ValueError("Exact installed identity required")
        provider = row["provider_identity"]
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
            raise ValueError("Independent provider identity and mapping review required")
        for value in provider.values():
            text(value)
        if row["currency"] != "USD" or row["original_money"] != row["value"]:
            raise ValueError("Original decimal USD amount required")
        number = shopping_math.amount(row["value"])
        if number == 0 and not field["zero_is_value"]:
            raise ValueError("Provider zero semantics unavailable")
        if type(row["estimated"]) is not bool or row["estimate_kind"] not in {"provider_guide", "observed"}:
            raise ValueError("Manufactured grade estimates are unsupported")
        if row["estimated"] != (row["estimate_kind"] == "provider_guide"):
            raise ValueError("Estimate status conflicts with evidence class")
        captured = timestamp(row["captured_at"])
        if captured > now or captured.strftime("%Y-%m") != package["release_month"]:
            raise ValueError("Capture time conflicts with the snapshot release")
        if row["as_of"] is not None:
            valued = date.fromisoformat(row["as_of"])
            if valued > captured.date():
                raise ValueError("Valuation date is later than capture")
        if build_reference:
            built = timestamp(row["publisher_built_at"])
            if row["as_of"] is not None or built > captured:
                raise ValueError("Build reference cannot invent a valuation date or future build")
            if row["reference_as_of"] != built.astimezone(timezone.utc).date().isoformat():
                raise ValueError("Reference date must be the UTC publisher build date")
        if not references.source_url(row["source_url"]):
            raise ValueError("Supported HTTPS source URL required")
        text(row["source_version"])
    return package


def source_packages(package):
    """Project each source to the preserved v1 contract; never pool its rights."""
    if package["schema"] == "dex-price-snapshot-v1":
        return {package["contract"]["review_id"]: package}
    return {
        key: dict(
            schema="dex-price-snapshot-v1",
            version=package["version"],
            release_month=package["release_month"],
            contract=value["contract"],
            expires_at=value["expires_at"],
            records=[
                {k: v for k, v in row.items() if k != "contract_id"}
                for row in package["records"]
                if row.get("contract_id") == key
            ],
        )
        for key, value in package["contracts"].items()
    }


def validate_sources(package, entries, *, now):
    if set(package) != {"schema", "version", "release_month", "contracts", "records"}:
        raise ValueError("Unsupported multi-source snapshot structure")
    contracts, rows = package["contracts"], package["records"]
    if not isinstance(contracts, dict) or not 1 <= len(contracts) <= 32:
        raise ValueError("One to 32 independent source contracts required")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("Snapshot needs a finite, nonempty record set")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("contract_id") not in contracts:
            raise ValueError("Observation must identify its own admitted source contract")
        oid = text(row.get("observation_id"))
        if oid in seen:
            raise ValueError("Duplicate observation identity across sources")
        seen.add(oid)
    for key, value in contracts.items():
        if not isinstance(value, dict) or set(value) != {"contract", "expires_at"}:
            raise ValueError("Each source requires its own contract and expiry")
        if not isinstance(value["contract"], dict) or key != value["contract"].get("review_id"):
            raise ValueError("Contract identity conflicts with its independently reviewed source")
    for source in source_packages(package).values():
        validate(source, entries, now=now)
    return package


def reason(row, printing, today):
    identity = row["identity"]
    provider = row["provider_identity"]
    if identity != {k: printing.get(k) for k in IDENTITY}:
        return "rejected_installed_identity"
    if row.get("match_scope") == "conditional_market":
        from .market_identity import applicable

        if row["grade"] != "raw" or "reference_as_of" not in row or not applicable(row, printing):
            return "rejected_unresolved_or_conflicting_variant"
        if provider["number"] != printing["collector_number"] or provider["set"] != printing["set_name"]:
            return "rejected_provider_identity"
        return shopping_math.fresh(reference_date(row), today.isoformat())
    # Missing catalog variant semantics cannot be inferred from provider labels.
    if any(
        not printing.get(k) or provider[k] != printing[k]
        for k in ("language", "edition", "finish", "variant")
    ):
        return "rejected_unresolved_or_conflicting_variant"
    if provider["number"] != printing["collector_number"] or provider["set"] != printing["set_name"]:
        return "rejected_provider_identity"
    return shopping_math.fresh(reference_date(row), today.isoformat())


def reference_date(row):
    """Only validated TCGCSV raw rows carry the separately approved build date."""
    return row.get("reference_as_of", row["as_of"])
