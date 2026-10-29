"""Explicit engineering preparation; never invoked by an application read."""


def enable_read_fixture(state, monkeypatch):
    """Upgrade an older isolated B2 fixture explicitly before V2 navigation."""
    from django.conf import settings

    from pokemon_hunter.beta import catalog_imports
    from pokemon_hunter.inventory import connect

    with connect(state["root"] / "inventory.db") as db:
        catalog_imports.initialize(db)
    monkeypatch.setattr(settings, "B4_ENABLED", True)
    prepare_reads(state)


def prepare_reads(cx):
    from test_ownership_declarations import migrate as declarations_migrate

    from pokemon_hunter.beta import account_read_build as accounts
    from pokemon_hunter.beta import account_read_schema as schema
    from pokemon_hunter.beta import catalog_read_build as catalogs
    from pokemon_hunter.beta.catalog_read_schema import migrate

    declarations_migrate(cx)
    migrate()
    catalogs.activate(catalogs.prepare())
    schema.migrate()
    accounts.prepare(cx["actor"])
    accounts.prepare(cx["member"])
