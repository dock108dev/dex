"""Controlled manual photo confirmation, without recognition or provider activity."""

from photo_batch_helpers import photos as photos
from photo_batch_helpers import selected
from test_account_reads import parity
from test_bulk_onboarding import b2 as b2
from test_bulk_onboarding import b3 as b3
from test_bulk_onboarding import b4 as b4
from test_bulk_onboarding import bulk as bulk
from test_bulk_onboarding import cx as cx
from test_bulk_onboarding import e1 as e1
from test_bulk_onboarding import env as env
from test_bulk_onboarding import snapshot as snapshot
from test_ownership_declarations import migrate as declarations_migrate
from test_photo_confirmation import photo_confirm

from pokemon_hunter.beta import account_read_build as accounts
from pokemon_hunter.beta import account_read_schema as schema
from pokemon_hunter.beta import catalog_read_build as catalog
from pokemon_hunter.beta import collection
from pokemon_hunter.beta.catalog_read_schema import migrate


def test_photo_confirmation_receipt_incremental_and_undo(photos):
    declarations_migrate(photos)
    migrate()
    catalog.activate(catalog.prepare())
    schema.migrate()
    accounts.prepare(photos["actor"])
    batch = selected(photos)
    op = photo_confirm(photos, batch)
    assert op["state"] == "confirmed"
    parity(photos)
    assert collection.confirm(photos["actor"], op["id"])["state"] == "confirmed"
    collection.undo(photos["actor"], op["id"])
    parity(photos)
