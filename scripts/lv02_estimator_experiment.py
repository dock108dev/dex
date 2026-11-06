"""Predeclared, authored-only estimator comparison; not empirical market calibration."""

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pokemon_hunter.beta import sold_estimates as sold

IDENTITY = dict(
    set_id="authored-fossil",
    collector_number="10",
    language="en",
    edition="unlimited",
    finish="holo",
    variant="holo",
    catalog_version="engineering-v1",
)
START = datetime(2026, 7, 1, 12, tzinfo=timezone.utc)


def authored_series(kind):
    rows = []
    for day in range(100):
        if kind == "sparse" and day % 10:
            continue
        amount = Decimal(20) + (Decimal(day) / 5 if kind == "trend" else Decimal(day % 3 - 1))
        if kind == "outlier" and day % 17 == 0:
            amount = Decimal(9000)
        row = dict(
            origin="authored-market",
            sale_id=f"{kind}-{day}",
            identity=IDENTITY,
            grade="raw",
            condition=None,
            sold_at=(START + timedelta(days=day)).isoformat(),
            captured_at=(START + timedelta(days=day)).isoformat(),
            amount=str(amount),
            shipping="4",
            currency="USD",
            quantity=1,
            amount_basis="item_excluding_shipping_tax",
            price_semantics="transaction_amount",
            accepted_offer=False,
            accepted_amount_known=False,
            source_url="https://example.test/authored",
        )
        rows.append(row)
        if kind == "duplicate" and day % 7 == 0:
            rows.extend([dict(row)] * 3)
        if kind == "unknown_offer" and day % 2 == 0:
            row["accepted_offer"] = True
    return rows


def experiment():
    results = []
    # Separate five earlier development cutoffs from five later evaluation cutoffs.
    # No coefficients are tuned or selected by this script.
    for policy in sold.policies():
        for phase, cuts in (("development", range(50, 75, 5)), ("holdout", range(75, 100, 5))):
            errors, effective, available, count = [], [], 0, 0
            strata = {}
            trimmed_errors = []
            for kind in ("stable", "trend", "outlier", "sparse", "duplicate", "unknown_offer"):
                rows = authored_series(kind)
                stratum_errors = []
                for cut in cuts:
                    now = START + timedelta(days=cut)
                    earlier = [r for r in rows if sold.rules.timestamp(r["sold_at"]) < now]
                    later = [
                        r
                        for r in rows
                        if now <= sold.rules.timestamp(r["sold_at"]) < now + timedelta(days=5)
                        and not r["accepted_offer"]
                    ]
                    # One target per original sale identity; no duplicate holdout weighting.
                    later = list({r["sale_id"]: r for r in later}.values())
                    result = sold.estimate(earlier, IDENTITY, now=now, policy=policy)
                    count += 1
                    if result["value"] is None or not later:
                        continue
                    available += 1
                    effective.append(Decimal(result["effective_sample_size"]))
                    residuals = [Decimal(result["value"]) - Decimal(r["amount"]) for r in later]
                    errors.extend(residuals)
                    stratum_errors.extend(residuals)
                    if policy == sold.Policy():
                        used = {r["sale_id"] for r in result["used_sale_ids"]}
                        values = sorted(
                            {
                                r["sale_id"]: Decimal(r["amount"]) for r in earlier if r["sale_id"] in used
                            }.values()
                        )
                        trim = len(values) // 10
                        central = values[trim:-trim] if trim else values
                        control = sum(central) / len(central)
                        trimmed_errors.extend(control - Decimal(r["amount"]) for r in later)
                strata[kind] = dict(
                    scored_transactions=len(stratum_errors),
                    median_absolute_error=str(sold.median([abs(v) for v in stratum_errors]))
                    if stratum_errors
                    else None,
                    median_signed_bias=str(sold.median(stratum_errors)) if stratum_errors else None,
                )
            results.append(
                dict(
                    strata=strata,
                    trimmed_mean_control=dict(
                        window_days=30,
                        minimum_unique=10,
                        trim_each_tail="0.10",
                        median_absolute_error=str(sold.median([abs(v) for v in trimmed_errors])),
                        median_signed_bias=str(sold.median(trimmed_errors)),
                    )
                    if trimmed_errors
                    else None,
                    policy=asdict(policy),
                    phase=phase,
                    eligible_forecasts=available,
                    attempted_forecasts=count,
                    scored_transactions=len(errors),
                    median_absolute_error=str(sold.median([abs(v) for v in errors])) if errors else None,
                    median_signed_bias=str(sold.median(errors)) if errors else None,
                    minimum_effective_sample_size=str(min(effective)) if effective else None,
                )
            )
    return dict(
        schema="dex-lv02-estimator-experiment-v1",
        evidence_class="authored_engineering_only",
        real_calibration=False,
        production_policy_selected=False,
        historical_guide_comparison="unmeasured",
        lookbacks=[30, 90],
        half_lives=[14, 30],
        minimum_unique=[5, 10],
        results=results,
    )


if __name__ == "__main__":
    print(json.dumps(experiment(), indent=2))
