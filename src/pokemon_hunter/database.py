import json
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from .models import Listing, Settings


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            ebay_item_id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
            listing_type TEXT NOT NULL, item_price TEXT, shipping_price TEXT, landed_price TEXT,
            card_count INTEGER, cost_per_card TEXT, purity TEXT, detected_sets TEXT, score REAL,
            first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, end_time TEXT,
            alert_status TEXT NOT NULL, payload TEXT NOT NULL,
            last_alert_at TEXT, last_alert_price TEXT, ending_reminded INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS listing_observations (
            id INTEGER PRIMARY KEY, ebay_item_id TEXT NOT NULL REFERENCES listings(ebay_item_id),
            observed_at TEXT NOT NULL, price TEXT, shipping TEXT, bid_count INTEGER, payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS observations_item ON listing_observations(ebay_item_id, observed_at);
        CREATE TABLE IF NOT EXISTS pokedex (
            dex_number INTEGER PRIMARY KEY, pokemon_name TEXT NOT NULL, generation INTEGER NOT NULL,
            owned INTEGER NOT NULL CHECK(owned IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
            status TEXT NOT NULL, observed INTEGER NOT NULL DEFAULT 0, alerted INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS digests (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, body TEXT NOT NULL,
            listings TEXT NOT NULL, delivered_at TEXT
        );
        """)

    def close(self):
        self.conn.close()

    def sync_pokedex(self, rows):
        with self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO pokedex VALUES (:dex_number,:pokemon_name,:generation,:owned)", rows
            )

    def start_run(self, now):
        with self.conn:
            return self.conn.execute(
                "INSERT INTO runs(started_at,status) VALUES (?,?)", (now.isoformat(), "RUNNING")
            ).lastrowid

    def finish_run(self, run_id, now, status, observed=0, alerted=0, notes=None):
        with self.conn:
            self.conn.execute(
                "UPDATE runs SET completed_at=?,status=?,observed=?,alerted=?,notes=? WHERE id=?",
                (now.isoformat(), status, observed, alerted, json.dumps(notes or []), run_id),
            )

    def observe(self, listing: Listing, now: datetime):
        old = self.conn.execute(
            "SELECT * FROM listings WHERE ebay_item_id=?", (listing.ebay_item_id,)
        ).fetchone()
        status = "ALERTED" if old and old["last_alert_at"] else "NEW"
        if not listing.qualifying:
            status = "EXPIRED" if listing.end_time and listing.end_time <= now else "REJECTED"

        def dec(v):
            return str(v) if v is not None else None

        with self.conn:
            self.conn.execute(
                """INSERT INTO listings
                (ebay_item_id,title,url,listing_type,item_price,shipping_price,landed_price,card_count,
                 cost_per_card,purity,detected_sets,score,first_seen_at,last_seen_at,end_time,alert_status,payload)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(ebay_item_id) DO UPDATE SET
                 title=excluded.title,url=excluded.url,listing_type=excluded.listing_type,
                 item_price=excluded.item_price,shipping_price=excluded.shipping_price,
                 landed_price=excluded.landed_price,card_count=excluded.card_count,
                 cost_per_card=excluded.cost_per_card,purity=excluded.purity,detected_sets=excluded.detected_sets,
                 score=excluded.score,last_seen_at=excluded.last_seen_at,end_time=excluded.end_time,
                 alert_status=excluded.alert_status,payload=excluded.payload""",
                (
                    listing.ebay_item_id,
                    listing.title,
                    listing.url,
                    listing.listing_type,
                    dec(listing.item_price),
                    dec(listing.shipping_price),
                    dec(listing.landed_price),
                    listing.count.denominator,
                    dec(listing.cost_per_card),
                    listing.purity,
                    json.dumps(sorted(listing.detected_sets)),
                    listing.pokedex_score,
                    now.isoformat(),
                    now.isoformat(),
                    listing.end_time.isoformat() if listing.end_time else None,
                    status,
                    listing.model_dump_json(),
                ),
            )
            self.conn.execute(
                "INSERT INTO listing_observations(ebay_item_id,observed_at,price,shipping,bid_count,payload) VALUES (?,?,?,?,?,?)",
                (
                    listing.ebay_item_id,
                    now.isoformat(),
                    dec(listing.item_price),
                    dec(listing.shipping_price),
                    listing.bid_count,
                    listing.model_dump_json(),
                ),
            )
        return old

    def due(self, listing: Listing, previous, settings: Settings, now: datetime) -> bool:
        if not listing.qualifying:
            return False
        if not previous or not previous["last_alert_at"]:
            return True
        if listing.listing_type == "bin":
            return False  # A rejected never-alerted listing still gets its first crossing alert.
        # Repeated manual runs do not create repeated auction alerts that day.
        if now - datetime.fromisoformat(previous["last_alert_at"]) < timedelta(hours=20):
            return False
        ending = listing.end_time and now < listing.end_time <= now + timedelta(hours=24)
        if ending and not previous["ending_reminded"]:
            return True
        old_price = Decimal(previous["last_alert_price"])
        return (
            old_price > 0
            and abs(listing.landed_price - old_price) / old_price >= settings.alerts.material_price_change
        )

    def expire(self, now):
        with self.conn:
            self.conn.execute(
                "UPDATE listings SET alert_status='EXPIRED' WHERE end_time IS NOT NULL AND end_time<=?",
                (now.isoformat(),),
            )

    def pending(self):
        return self.conn.execute(
            "SELECT * FROM digests WHERE delivered_at IS NULL ORDER BY created_at"
        ).fetchall()

    def queue(self, digest_id, now, body, listings):
        with self.conn:
            self.conn.execute(
                "INSERT INTO digests VALUES (?,?,?,?,NULL)",
                (digest_id, now.isoformat(), body, json.dumps([x.model_dump(mode="json") for x in listings])),
            )

    def delivered(self, digest_id: str, now: datetime):
        row = self.conn.execute("SELECT * FROM digests WHERE id=?", (digest_id,)).fetchone()
        with self.conn:
            self.conn.execute("UPDATE digests SET delivered_at=? WHERE id=?", (now.isoformat(), digest_id))
            for data in json.loads(row["listings"]):
                item = Listing.model_validate(data)
                ending = bool(item.end_time and item.end_time <= now + timedelta(hours=24))
                self.conn.execute(
                    """UPDATE listings SET alert_status='ALERTED',last_alert_at=?,
                     last_alert_price=?,ending_reminded=MAX(ending_reminded,?) WHERE ebay_item_id=?""",
                    (now.isoformat(), str(item.landed_price), int(ending), item.ebay_item_id),
                )
