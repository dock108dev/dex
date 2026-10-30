"""Backend-only primitives for private account reads. These do not establish access or possession.

Consumers must hold an ordinary authorized operation and perform the final authority
check. No HTTP selector can choose retained scope or another account's revision.
"""

import json
from dataclasses import dataclass

from . import collection, store
from .catalog_read_build import Unavailable, active, digest, revision
from .catalog_read_select import offset


@dataclass(frozen=True)
class CatalogSnapshot:
    build: int
    authority_revision: int
    token: str


def current():
    manifest, token = active()
    return CatalogSnapshot(manifest["id"], manifest["revision"], token)


def finish(snapshot):
    manifest, token = active(snapshot.token)
    if revision() != snapshot.authority_revision or manifest["id"] != snapshot.build:
        raise collection.Conflict("Catalog snapshot changed")


def printing_metadata(snapshot, printing_ids):
    """Exact bounded typed metadata, including archived and unresolved identities."""
    ids = tuple(dict.fromkeys(printing_ids))
    if len(ids) > 100 or any(not isinstance(key, str) for key in ids):
        raise ValueError("Select at most 100 literal printings")
    if not ids:
        return []
    rows = store.rows(
        "SELECT id,group_id,published,payload,sha FROM cr_printings WHERE build=%s AND scope IN ('retained','shared') AND id IN ("
        + ",".join(["%s"] * len(ids))
        + ") ORDER BY id",
        [snapshot.build, *ids],
    )
    result = []
    for row in rows:
        if digest(row["payload"]) != row["sha"]:
            raise Unavailable("corrupt_printing")
        result.append(
            dict(
                printing=json.loads(row["payload"]),
                group_id=row["group_id"],
                published=bool(row["published"]),
            )
        )
    finish(snapshot)
    return result


def alias_candidates(snapshot, alias, *, page=1, size=40):
    if (
        not isinstance(alias, str)
        or not alias
        or len(alias) > 160
        or type(page) is not int
        or page < 1
        or type(size) is not int
        or not 1 <= size <= 100
    ):
        raise ValueError("Choose a bounded literal alias page")
    total = store.rows(
        "SELECT COUNT(*) AS n FROM cr_aliases WHERE build=%s AND scope IN ('retained','shared') AND alias=%s",
        [snapshot.build, alias],
    )[0]["n"]
    rows = store.rows(
        "SELECT printing_id FROM cr_aliases WHERE build=%s AND scope IN ('retained','shared') AND alias=%s ORDER BY printing_id LIMIT %s OFFSET %s",
        [snapshot.build, alias, size, offset(page, size)],
    )
    finish(snapshot)
    return dict(total=total, printing_ids=[r["printing_id"] for r in rows], page=page, page_size=size)


def account_key(actor):
    """Revision infrastructure only; callers add effective-source and ownership keys."""
    actor = store.verified(actor)
    rows = store.rows("SELECT value FROM account_read_revisions WHERE user_id=%s", [actor.user_id])
    return dict(
        internal_account_id=actor.user_id,
        collection_generation=collection.generation(actor),
        account_read_revision=rows[0]["value"] if rows else 0,
    )
