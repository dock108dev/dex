"""Versioned per-printing evidence, independent of lot arithmetic and presentation.

All inputs are admitted by the existing snapshot lifecycle. This module owns no
store or provider. Legacy v1 observations remain guides, never fabricated sales.
"""

from datetime import timedelta, timezone

from . import price_snapshot_contract as rules
from . import sold_estimates

SCHEMA = "dex-valuation-evidence-v2"
NATIVE_SCHEMA = "dex-valuation-evidence-v3"
NATIVE = "publisher_native_guide"
NATIVE_AMOUNT = "publisher_native_unresolved_shipping_tax"
NATIVE_MONEY = dict(
    currency="USD", unit="one_physical_card", shipping="unknown", tax="unknown", adjustment="none"
)


def is_native(row):
    """Recognize native evidence before any legacy/normalized consumer fallback."""
    nested = row.get("raw_record")
    for value in (row, nested if isinstance(nested, dict) else {}):
        evidence = value.get("evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        if (
            value.get("basis") == NATIVE
            or value.get("amount_basis") == NATIVE_AMOUNT
            or evidence.get("basis") == NATIVE
            or evidence.get("schema") == NATIVE_SCHEMA
        ):
            return True
    return False


def native_contract(policy):
    spec = policy.get("valuation")
    required = {
        "basis",
        "condition",
        "amount_basis",
        "native_money",
        "ceiling_applicable",
        "qualification",
        "qualification_review",
        "estimator",
        "sale_origins",
    }
    if not isinstance(spec, dict) or set(spec) != required:
        raise ValueError("Explicit native-guide valuation policy required")
    if (
        spec["basis"] != NATIVE
        or spec["condition"] is not None
        or spec["amount_basis"] != NATIVE_AMOUNT
        or spec["native_money"] != NATIVE_MONEY
        or spec["ceiling_applicable"] is not False
        or spec["estimator"] is not None
        or spec["sale_origins"] != []
        or spec["qualification"] not in {"engineering_only", "reviewed"}
    ):
        raise ValueError("Native guides preserve unknown money basis and cannot normalize or estimate sales")
    rules.text(spec["qualification_review"])
    if any(f["grade"] != "raw" for f in policy["fields"].values()):
        raise ValueError("Native guides require raw references")
    return spec


def native_context(policy):
    return dict(provider=policy["provider"], policy_version=policy["policy_version"], fields=policy["fields"])


def native_cohort(row):
    context = row.get("_native_context")
    if not context or not is_native(row):
        raise ValueError("Admitted native source context required")
    return rules.digest(
        dict(
            provider=context["provider"],
            policy_version=context["policy_version"],
            field=row["field"],
            field_policy=context["fields"][row["field"]],
            currency=row["currency"],
            evidence={k: row["evidence"][k] for k in ("basis", "condition", "amount_basis", "native_money")},
            reference_date=rules.reference_date(row),
            publisher_built_at=row.get("publisher_built_at"),
        )
    )


def contract(policy):
    if policy.get("schema") == "dex-price-contract-v3":
        return native_contract(policy)
    evidence = policy.get("valuation")
    if not isinstance(evidence, dict) or set(evidence) != {
        "basis",
        "condition",
        "amount_basis",
        "ceiling_applicable",
        "qualification",
        "qualification_review",
        "estimator",
        "sale_origins",
    }:
        raise ValueError("Explicit v2 valuation policy required")
    if (
        evidence["basis"] not in {"guide", "sold_estimate"}
        or evidence["condition"] not in sold_estimates.CONDITIONS
    ):
        raise ValueError("Unsupported evidence basis or condition")
    if (
        evidence["amount_basis"] != "item_excluding_shipping_tax"
        or type(evidence["ceiling_applicable"]) is not bool
    ):
        raise ValueError("Explicit item-only monetary basis required")
    if evidence["qualification"] not in {"engineering_only", "reviewed"}:
        raise ValueError("Explicit calibration qualification required")
    rules.text(evidence["qualification_review"])
    if any(field["grade"] != "raw" for field in policy["fields"].values()):
        raise ValueError("V2 valuation currently supports raw references only")
    if evidence["basis"] == "sold_estimate":
        if evidence["ceiling_applicable"] or any(
            f.get("date_basis", "valuation") != "valuation" for f in policy["fields"].values()
        ):
            raise ValueError("Sold medians are not strict ceilings or publisher guides")
        sold_estimates.Policy(**evidence["estimator"])
        origins = evidence["sale_origins"]
        if not isinstance(origins, list) or not 1 <= len(origins) <= 8 or len(set(origins)) != len(origins):
            raise ValueError("Finite independently reviewed original sale sources required")
        for origin in origins:
            rules.text(origin)
    elif evidence["estimator"] is not None or evidence["sale_origins"] != []:
        raise ValueError("Guides cannot invent transactions or estimator parameters")
    if any(field.get("identity_scope") == "conditional_market" for field in policy["fields"].values()) and (
        evidence["condition"] is not None or evidence["ceiling_applicable"]
    ):
        raise ValueError("Mixed-condition market guides cannot assert a condition or ceiling")
    if evidence["ceiling_applicable"] and evidence["condition"] is None:
        raise ValueError("Condition-specific ceiling applicability required")
    return evidence


def validate(row, policy, *, expiry, now):
    spec = contract(policy)
    evidence = row["evidence"]
    native = policy["schema"] == "dex-price-contract-v3"
    if not isinstance(evidence, dict) or set(evidence) != (
        {
            "schema",
            "basis",
            "condition",
            "amount_basis",
            "sales",
            "estimate",
        }
        | ({"native_money"} if native else set())
    ):
        raise ValueError("Versioned evidence envelope required")
    if evidence["schema"] != (NATIVE_SCHEMA if native else SCHEMA) or any(
        evidence[k] != spec[k] for k in ("basis", "condition", "amount_basis")
    ):
        raise ValueError("Evidence differs from admitted valuation policy")
    if (
        row["condition"] != spec["condition"]
        or type(row["ceiling_applicable"]) is not bool
        or row["ceiling_applicable"] != spec["ceiling_applicable"]
    ):
        raise ValueError("Condition/ceiling scope differs from admission")
    if row["valuation_qualification"] != spec["qualification"]:
        raise ValueError("Qualification differs from independent review")
    if native and evidence["native_money"] != spec["native_money"]:
        raise ValueError("Native money basis differs from admission")
    if spec["basis"] in {"guide", NATIVE}:
        if (
            evidence["sales"] != []
            or evidence["estimate"] is not None
            or row["estimate_kind"] != "provider_guide"
        ):
            raise ValueError("Guide evidence cannot manufacture sale history")
        return
    if row["estimate_kind"] != "dex_sold_estimate" or row.get("match_scope"):
        raise ValueError("Sold estimates require exact printing evidence")
    calculated = rules.timestamp(evidence["estimate"]["calculated_at"]).astimezone(timezone.utc)
    if calculated > now or calculated < rules.timestamp(row["captured_at"]):
        raise ValueError("Calculation and capture times conflict")
    if any(s.get("origin") not in spec["sale_origins"] for s in evidence["sales"]):
        raise ValueError("A contributing sale lacks independent source scope")
    result = sold_estimates.estimate(
        evidence["sales"],
        row["identity"],
        now=calculated,
        policy=sold_estimates.Policy(**spec["estimator"]),
        condition=spec["condition"],
    )
    if result != evidence["estimate"] or result["value"] is None or result["value"] != row["value"]:
        raise ValueError("Sold estimate differs from its reproducible evidence")
    if row["as_of"] != rules.timestamp(result["sold_through"]).astimezone(timezone.utc).date().isoformat():
        raise ValueError("Calculation cannot refresh sale dates")
    latest_capture = max(rules.timestamp(s["captured_at"]) for s in evidence["sales"])
    if rules.timestamp(row["captured_at"]) != latest_capture:
        raise ValueError("Preserve original source capture time")
    oldest = rules.timestamp(result["sold_from"])
    deadline = min(calculated + timedelta(days=1), oldest + timedelta(days=spec["estimator"]["window_days"]))
    if expiry is None or rules.timestamp(expiry) > deadline:
        raise ValueError("Sold estimate expiry exceeds its daily/lookback bound")


def select(printing, rows, *, today, condition=None, purpose="normalized"):
    """Sold-first choice from currently admitted rows. Caller revalidates at use.

    No guide and its underlying sales are added or averaged. Generic condition
    references remain useful broad benchmarks; known condition-specific references
    require a matching request. Engineering-only evidence never becomes usable here.
    """
    if purpose not in {"normalized", "native"}:
        raise ValueError("Explicit reference purpose required")
    eligible = []
    for row in rows:
        if is_native(row) != (purpose == "native"):
            continue
        if row.get("printing_id") != printing["id"] or row.get("grade") != "raw":
            continue
        if row.get("valuation_qualification", "reviewed") != "reviewed":
            continue
        if row.get("condition") is not None and row["condition"] != condition:
            continue
        if rules.reason(row, printing, today) == "eligible":
            eligible.append(row)
    if not eligible:
        return dict(
            schema=SCHEMA, reference=None, basis=None, coverage="unavailable", strict_ceiling_ready=False
        )
    row = max(
        eligible,
        key=lambda r: (
            r["estimate_kind"] == "dex_sold_estimate",
            rules.reference_date(r),
            rules.timestamp(r["captured_at"]),
            r.get("_contract_sha256", ""),
            r["observation_id"],
        ),
    )
    return dict(
        schema=SCHEMA,
        reference=row,
        basis=NATIVE
        if is_native(row)
        else "sold_estimate"
        if row["estimate_kind"] == "dex_sold_estimate"
        else "guide",
        coverage="per_printing",
        strict_ceiling_ready=bool(
            condition and row.get("condition") == condition and row.get("ceiling_applicable") is True
        ),
    )


def lot_basis(bases):
    """Evidence classification only. Coverage and lot money belong to LV-05."""
    values = set(bases)
    if not values <= {"guide", "sold_estimate"}:
        raise ValueError("Unsupported evidence basis")
    return "mixed" if len(values) > 1 else next(iter(values), None)
