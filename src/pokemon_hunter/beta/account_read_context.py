"""Shared authorization, revision checks and bounded payloads for private V2 reads."""

import json
from functools import wraps
from urllib.parse import urlencode

from django.db import DatabaseError

from . import account_read_build as builds
from . import account_read_schema as schema
from . import card_groups, collection, store
from .catalog_read_build import Unavailable, active
from .catalog_read_snapshot import snapshot

BASE = "/api/v2/"


def url(state, path, **params):
    return (
        BASE
        + path
        + "?"
        + urlencode(
            dict(
                catalog_revision=state["catalog_token"],
                generation=state["generation"],
                account_revision=state["seal"],
                **params,
            )
        )
    )


def read(fn):
    @wraps(fn)
    def wrapped(actor, raw=None, **kwargs):
        actor = store.verified(actor)
        raw = dict(raw or {})
        selectors = {
            key: raw.pop(key) for key in ("catalog_revision", "generation", "account_revision") if key in raw
        }
        if any(not isinstance(v, str) or len(v) > 160 for v in selectors.values()):
            raise ValueError("Choose short revision selectors")
        if "generation" in selectors:
            card_groups._integer(selectors["generation"], "generation", 0)
        try:
            with snapshot():
                manifest, token = active(selectors.get("catalog_revision"))
                schema.check()
                state = builds.state(
                    actor,
                    token,
                    requested_generation=selectors.get("generation"),
                    requested_revision=selectors.get("account_revision"),
                )
                current = (state["generation"], state["revision"])
                state["catalog_stride"] = manifest["stride"]
                result = fn(actor, manifest["id"], state, raw, **kwargs)
            store.verified(actor)
            final = store.rows(
                "SELECT COALESCE((SELECT value FROM collection_generations WHERE user_id=%s),0) AS generation,COALESCE((SELECT value FROM account_read_revisions WHERE user_id=%s),0) AS revision,(SELECT value FROM catalog_read_revision WHERE id=1) AS catalog,(SELECT status FROM account_read_state WHERE user_id=%s) AS status",
                [actor.user_id] * 3,
            )[0]
            if (final["generation"], final["revision"]) != current or final["catalog"] != manifest[
                "revision"
            ]:
                raise collection.Conflict("Read revision changed")
            if final["status"] != "ready":
                raise Unavailable("account_state_changed")
            result.update(
                read_version=2,
                public=False,
                catalog_revision=token,
                account_revision=state["seal"],
                account_id=actor.user_id,
                generation=current[0],
            )
            return result
        except (DatabaseError, IndexError, KeyError, json.JSONDecodeError) as exc:
            raise Unavailable("account_integrity") from exc

    return wrapped


def payload(row, state, kind, *, full=False):
    if row["payload"] is None or (not full and len(row["payload"].encode()) > 1100):
        return dict(id=row["id"], oversized=True, url=url(state, f"resources/{kind}/{row['id']}/"))
    return builds.decode(row)


def page_result(items, field, total, page, size):
    return {
        field: items,
        "total": total,
        "page": page,
        "page_size": size,
        "pages": (total + size - 1) // size,
    }
