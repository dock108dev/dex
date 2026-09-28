import copy
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import synthetic_collection

from pokemon_hunter.database import Database
from pokemon_hunter.normalize import evaluate
from pokemon_hunter.notifier import Notifier
from pokemon_hunter.pokedex import missing_rates, summary
from pokemon_hunter.runner import run, run_lock

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pokedex():
    return [
        {
            "dex_number": n,
            "pokemon_name": row["name"],
            "generation": row["generation"],
            "owned": n <= 133 or 152 <= n <= 171,
        }
        for key, row in synthetic_collection()["pokedex"].items()
        for n in [int(key)]
    ]


def test_collection_is_exact(pokedex):
    assert summary(pokedex) == "Kanto 133/151 · Johto 20/100 · Total 153/251 · Missing 98"
    assert missing_rates(pokedex) == (18 / 151, 0.8)
    assert pokedex[170]["owned"] is True
    assert pokedex[250]["owned"] is False


def test_repeat_no_spam_and_observations(tmp_path, settings, catalog, pokedex, raw, now):
    db = tmp_path / "demo.db"
    notifier = Notifier(tmp_path / "reports")
    first = run(db, settings, catalog, [], pokedex, notifier, fixtures=[raw, raw], now=now)
    second = run(db, settings, catalog, [], pokedex, notifier, fixtures=[raw], now=now + timedelta(days=1))
    assert first["alerted"] == 1 and first["observed"] == 1
    assert second["alerted"] == 0
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM listings").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM listing_observations").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM pokedex").fetchone()[0] == 251
        assert conn.execute("SELECT alert_status FROM listings").fetchone()[0] == "ALERTED"


def test_price_drop_crossing(tmp_path, settings, catalog, pokedex, raw, now):
    db, notifier = tmp_path / "demo.db", Notifier(tmp_path / "reports")
    raw["price"]["value"] = "200"
    assert run(db, settings, catalog, [], pokedex, notifier, fixtures=[raw], now=now)["alerted"] == 0
    assert not (tmp_path / "reports").exists()
    raw["price"]["value"] = "20"
    assert run(db, settings, catalog, [], pokedex, notifier, fixtures=[raw], now=now)["alerted"] == 1


class FailingNotifier:
    def send(self, *args):
        raise RuntimeError("Synthetic delivery failure")


def test_failed_delivery_retry_merges_into_one_digest(tmp_path, settings, catalog, pokedex, raw, now):
    path = tmp_path / "demo.db"
    with pytest.raises(RuntimeError, match="Synthetic"):
        run(path, settings, catalog, [], pokedex, FailingNotifier(), fixtures=[raw], now=now)
    db = Database(path)
    assert db.conn.execute("SELECT last_alert_at FROM listings").fetchone()[0] is None
    old_id = db.pending()[0]["id"]
    db.close()
    second = {**raw, "itemId": "second"}
    result = run(
        path, settings, catalog, [], pokedex, Notifier(tmp_path / "reports"), fixtures=[raw, second], now=now
    )
    assert result["alerted"] == 2
    assert len(result["reports"]) == 1
    assert old_id in result["reports"][0]


def test_failed_delivery_does_not_send_stale_price(tmp_path, settings, catalog, pokedex, raw, now):
    path = tmp_path / "demo.db"
    with pytest.raises(RuntimeError):
        run(path, settings, catalog, [], pokedex, FailingNotifier(), fixtures=[raw], now=now)
    raw["price"]["value"] = "300"
    result = run(
        path, settings, catalog, [], pokedex, Notifier(tmp_path / "reports"), fixtures=[raw], now=now
    )
    assert result["alerted"] == 0


def test_auction_ending_reminder_once(tmp_path, settings, catalog, now, raw):
    raw.update(
        buyingOptions=["AUCTION"],
        currentBidPrice={"value": "20", "currency": "USD"},
        itemEndDate=(now + timedelta(hours=48)).isoformat(),
    )
    db = Database(tmp_path / "demo.db")
    item = evaluate(raw, settings, catalog, (0.12, 0.8), now)
    previous = db.observe(item, now)
    assert db.due(item, previous, settings, now)
    db.queue("first", now, "", [item])
    db.delivered("first", now)
    previous = db.observe(item, now)
    assert not db.due(item, previous, settings, now + timedelta(hours=1))
    later = now + timedelta(hours=25)
    assert db.due(item, previous, settings, later)
    db.queue("second", later, "", [item])
    db.delivered("second", later)
    previous = db.observe(item, later)
    assert not db.due(item, previous, settings, later + timedelta(hours=21))
    db.close()


def test_digest_limit_unalerted_can_show_tomorrow(tmp_path, settings, catalog, pokedex, raw, now):
    items = [{**raw, "itemId": str(i)} for i in range(8)]
    path, notifier = tmp_path / "demo.db", Notifier(tmp_path / "reports")
    assert run(path, settings, catalog, [], pokedex, notifier, fixtures=items, now=now)["alerted"] == 5
    assert (
        run(path, settings, catalog, [], pokedex, notifier, fixtures=items, now=now + timedelta(days=1))[
            "alerted"
        ]
        == 3
    )


def test_failed_search_not_reported_as_no_hits(tmp_path, settings, catalog, pokedex, now):
    class BrokenClient:
        def search(self, *args):
            raise RuntimeError("Synthetic API failure")

    path = tmp_path / "demo.db"
    with pytest.raises(RuntimeError):
        run(
            path,
            settings,
            catalog,
            ["neo"],
            pokedex,
            Notifier(tmp_path / "reports"),
            client=BrokenClient(),
            now=now,
        )
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT status FROM runs").fetchone()[0] == "FAILED"


def test_live_description_rechecked(tmp_path, settings, catalog, pokedex, raw, now):
    class FakeClient:
        warnings = []

        def search(self, *args):
            yield copy.deepcopy(raw)

        def detail(self, item_id):
            return {"description": "This is a custom pack with guaranteed holo."}

    result = run(
        tmp_path / "demo.db",
        settings,
        catalog,
        ["neo"],
        pokedex,
        Notifier(tmp_path / "reports"),
        client=FakeClient(),
        now=now,
    )
    assert result["alerted"] == 0


def test_no_overlapping_runs(tmp_path):
    with run_lock(tmp_path / "demo.db"):
        with pytest.raises(RuntimeError, match="already active"):
            with run_lock(tmp_path / "demo.db"):
                pass


def test_money_stored_exactly(tmp_path, settings, catalog, raw, now):
    db = Database(tmp_path / "demo.db")
    raw["price"]["value"] = "39.99"
    item = evaluate(raw, settings, catalog, (0.12, 0.8), now)
    db.observe(item, now)
    row = db.conn.execute("SELECT * FROM listings").fetchone()
    assert row["landed_price"] == "44.99"
    assert json.loads(row["payload"])["item_price"] == "39.99"
    db.close()
