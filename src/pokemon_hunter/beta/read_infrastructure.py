"""Fixed-size schema-object checks; no scan of catalog or account records."""

from . import account_read_schema as accounts
from . import catalog_read_schema as catalog
from . import store
from .catalog_read_build import Unavailable

CATALOG_INDEXES = (
    "cr_gram_rowid",
    "cr_gram_lookup",
    "cr_public_species",
    "cr_printing_unresolved",
    "cr_group_species",
    "cr_child_group",
    *(
        f"cr_{kind}_{sort}"
        for kind in ("public_order", "order", "public_match")
        for sort in ("set", "name", "number")
    ),
    *(f"cr_{kind}_{field}" for kind in ("match", "child") for field in ("edition", "finish", "variant")),
)
ACCOUNT_INDEXES = (
    *(f"{table}_count" for table in accounts.TABLES),
    *(
        f"{table}_component"
        for table in (
            "ar_groups",
            "ar_cards",
            "ar_copies",
            "ar_evidence",
            "ar_artwork",
            "ar_membership",
            "ar_scope_owned",
            "ar_variant_ownership",
        )
    ),
    *(
        f"ar_membership_{scope}_{sort}"
        for scope in ("present", "available")
        for sort in ("set", "name", "number")
    ),
    *(f"ar_retained_order_{sort}" for sort in ("set", "name", "number")),
    "ar_scope_species",
    "ar_scope_date_counts_species",
    "ar_scope_set_names",
    "ar_scope_dates",
    "ar_scope_set_options",
    "ar_catalog_component",
    "ar_catalog_literal",
    "ar_dependency_operation",
    "ar_owned",
    "ar_available",
    "ar_retained_identity",
    "ar_scope_owned_dates",
    "ar_copy_state",
    "ar_private_picker",
    "ar_copy_group",
    "ar_copy_printing",
    "ar_scope_owned_species",
    "ar_card_species",
    "ar_card_literal",
    "ar_evidence_group",
    "ar_evidence_links_component",
    "ar_goal_lookup",
    "ar_goal_species",
)


def check(*, account=False):
    tables = (
        (
            tuple(accounts.TABLES)
            + (
                "account_read_state",
                "ar_catalog",
                "ar_scope_catalog",
                "ar_scope_date_counts",
                "ar_scope_options",
            )
        )
        if account
        else (
            tuple(catalog.TABLES)
            + ("catalog_read_revision", "catalog_read_active", "catalog_read_builds", "cr_gram_index")
        )
    )
    indexes = ACCOUNT_INDEXES if account else CATALOG_INDEXES
    expected = {(name, "table") for name in tables} | {(name, "index") for name in indexes}
    names = [name for name, _ in expected]
    found = store.rows(
        "SELECT name,type FROM sqlite_master WHERE name IN (" + ",".join(["%s"] * len(names)) + ")", names
    )
    if {(row["name"], row["type"]) for row in found} != expected:
        raise Unavailable("infrastructure_missing")
