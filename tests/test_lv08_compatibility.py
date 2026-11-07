"""Disposable read-schema transition and rollback preservation checks."""

import pytest
from django.db import connection
from test_account_reads import b2 as b2
from test_account_reads import b3 as b3
from test_account_reads import b4 as b4
from test_account_reads import cx as cx
from test_account_reads import e1 as e1
from test_account_reads import env as env
from test_account_reads import prepared as prepared
from test_account_reads import snapshot as snapshot

from pokemon_hunter.beta import account_read_build as builds
from pokemon_hunter.beta import account_read_schema as schema
from pokemon_hunter.beta import store


def protected_tables():
    return {
        name: store.rows(f'SELECT * FROM "{name}"')
        for name in connection.introspection.table_names()
        if not name.startswith("ar_") and name not in {"account_read_schema", "account_read_state"}
    }


@pytest.mark.parametrize("previous", [2, 3])
def test_transition_requires_preparation_and_preserves_authority(prepared, previous):
    from pokemon_hunter.beta.catalog_read_build import Unavailable

    actor = prepared["actor"]
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE ar_shopping_picker")
        if previous == 2:
            cursor.execute("DROP TABLE ar_shopping_names")
        cursor.execute("UPDATE account_read_schema SET version=%s", [previous])
        cursor.execute("UPDATE account_read_state SET policy='previous-policy'")
    before = protected_tables()
    with pytest.raises(Unavailable, match="incompatible_schema"):
        schema.check()
    schema.migrate()
    assert protected_tables() == before
    schema.check()
    with pytest.raises(Unavailable, match="account_policy_incompatible"):
        builds.state(actor, builds.catalog_current().token)
    builds.prepare(actor)
    assert builds.state(actor, builds.catalog_current().token)["status"] == "ready"
    assert protected_tables() == before


def test_retirement_preserves_authority_and_requires_explicit_repreparation(prepared):
    actor = prepared["actor"]
    before = protected_tables()
    schema.retire()
    assert protected_tables() == before
    assert "account_read_schema" not in connection.introspection.table_names()
    assert not any(n.startswith("ar_") for n in connection.introspection.table_names())
    schema.migrate()
    builds.prepare(actor)
    assert builds.state(actor, builds.catalog_current().token)["status"] == "ready"
    assert protected_tables() == before


def test_retirement_rejects_unknown_schema_without_changes(prepared):
    with connection.cursor() as cursor:
        cursor.execute("UPDATE account_read_schema SET version=99")
    before = {n: store.rows(f'SELECT * FROM "{n}"') for n in connection.introspection.table_names()}
    with pytest.raises(ValueError, match="exact current"):
        schema.retire()
    assert before == {n: store.rows(f'SELECT * FROM "{n}"') for n in connection.introspection.table_names()}


def test_retirement_failure_rolls_back_all_derived_tables(prepared):
    before = {n: store.rows(f'SELECT * FROM "{n}"') for n in connection.introspection.table_names()}

    def interrupted(execute, sql, params, many, context):
        if sql == "DROP TABLE IF EXISTS account_read_state":
            raise RuntimeError("authored interruption")
        return execute(sql, params, many, context)

    with connection.execute_wrapper(interrupted), pytest.raises(RuntimeError, match="authored"):
        schema.retire()
    assert before == {n: store.rows(f'SELECT * FROM "{n}"') for n in connection.introspection.table_names()}
