"""Provider and spending configuration policy, independent of storage/profile."""

import math


def validate(value, *, require_complete=False):
    """Return a validated copy; persistent/copy inputs may not invent missing fields."""
    if not isinstance(value, dict):
        raise ValueError("Invalid scan configuration")
    if require_complete and not {"enabled", "mode", "ceiling_usd", "user_ceiling_usd"} <= value.keys():
        raise ValueError("Invalid persistent scan configuration")
    value = {"enabled": True, "mode": "manual", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5, **value}
    if (
        not isinstance(value["mode"], str)
        or value["mode"] not in {"manual", "fixture", "openai", "codex_cli"}
        or type(value["enabled"]) is not bool
    ):
        raise ValueError("Invalid scan configuration")
    for key, limit in (("ceiling_usd", 1.0), ("user_ceiling_usd", 0.5)):
        try:
            amount = float(value[key])
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Invalid recognition spend ceiling") from None
        if isinstance(value[key], bool) or not math.isfinite(amount) or not 0 <= amount <= limit:
            raise ValueError("Recognition ceilings cannot exceed existing limits")
        value[key] = amount
    return value
