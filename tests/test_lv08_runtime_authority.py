"""Real session authorization must preserve an active indexed read transaction."""

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from test_account_reads import b2 as b2
from test_account_reads import b3 as b3
from test_account_reads import b4 as b4
from test_account_reads import cx as cx
from test_account_reads import e1 as e1
from test_account_reads import env as env
from test_account_reads import prepared as prepared
from test_account_reads import snapshot as snapshot

from pokemon_hunter.beta import discovery, store


@pytest.mark.parametrize("revoked", [False, True])
def test_authorization_preserves_transaction_and_checks_real_session(prepared, revoked):
    from django.contrib.sessions.models import Session

    actor = prepared["actor"]
    session = prepared["a"].session.session_key
    assert Session.objects.filter(session_key=session).exists()
    if revoked:
        Session.objects.filter(session_key=session).delete()
    with transaction.atomic():
        if revoked:
            with pytest.raises(PermissionDenied):
                discovery._authorize(actor, session)
        else:
            discovery._authorize(actor, session)
        assert not connection.closed_in_transaction
        assert store.principal(actor.subject) == actor
    assert store.principal(actor.subject) == actor


@pytest.mark.parametrize("revoked_at_publication", [False, True])
def test_indexed_session_checks_are_scoped_and_revalidated_after_publication(
    prepared, monkeypatch, revoked_at_publication
):
    from django.contrib.sessions.models import Session

    from pokemon_hunter.beta import shopping_index

    actor = prepared["actor"]
    session = prepared["a"].session.session_key
    original = discovery._session_current
    calls = []

    def checked(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(discovery, "_session_current", checked)

    @shopping_index.indexed
    def read(who):
        discovery._authorize(who, session)
        discovery._authorize(who, session)
        assert len(calls) == 1
        if revoked_at_publication:
            shopping_index.current(who).publication_checks.append(
                lambda: Session.objects.filter(session_key=session).delete()
            )
        return {}

    if revoked_at_publication:
        with pytest.raises(PermissionDenied):
            read(actor)
    else:
        read(actor)
    assert len(calls) == 2
