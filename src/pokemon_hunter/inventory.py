"""Game-neutral B0 storage. No authentication or live-app cutover."""

import sqlite3
import uuid

SCHEMA_VERSION = 1
NAMESPACE = uuid.UUID("c40655cd-2748-49cc-877f-88c05d3a4473")


def stable_id(kind, key):
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


OWNER_ID = stable_id("user", "legacy-local-owner")


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY);
    INSERT OR IGNORE INTO schema_versions VALUES(1);
    CREATE TABLE IF NOT EXISTS users(
      id TEXT PRIMARY KEY, auth_subject TEXT UNIQUE, login_name TEXT,
      role TEXT NOT NULL, state TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS games(
      id TEXT PRIMARY KEY, game_key TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
      adapter_version TEXT NOT NULL, capabilities TEXT NOT NULL, release_state TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS catalog_sets(
      id TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id), name TEXT NOT NULL,
      language TEXT, region TEXT, aliases TEXT NOT NULL, release_metadata TEXT NOT NULL,
      catalog_version TEXT NOT NULL, coverage_status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS printings(
      id TEXT PRIMARY KEY, set_id TEXT NOT NULL REFERENCES catalog_sets(id),
      collector_number TEXT NOT NULL, language TEXT, edition TEXT, finish TEXT, variant TEXT,
      unresolved_fields TEXT NOT NULL, attributes TEXT NOT NULL, provenance TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS external_mappings(
      provider TEXT NOT NULL, entity_kind TEXT NOT NULL, external_id TEXT NOT NULL,
      internal_id TEXT NOT NULL, PRIMARY KEY(provider,entity_kind,external_id));
    CREATE TABLE IF NOT EXISTS import_batches(
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
      source_hash TEXT NOT NULL, importer_version TEXT NOT NULL, state TEXT NOT NULL,
      UNIQUE(user_id,source_hash));
    CREATE TABLE IF NOT EXISTS binders(
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL,
      UNIQUE(id,user_id));
    CREATE TABLE IF NOT EXISTS owned_copies(
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
      printing_id TEXT REFERENCES printings(id), provisional_identity TEXT,
      binder_id TEXT, condition TEXT, purchase_amount TEXT, purchase_currency TEXT,
      purchase_date TEXT, notes TEXT, grading_company TEXT, grade TEXT, certificate TEXT,
      batch_id TEXT NOT NULL REFERENCES import_batches(id), legacy_id TEXT,
      first_edition_selected INTEGER NOT NULL CHECK(first_edition_selected IN (0,1)),
      state TEXT NOT NULL DEFAULT 'active',
      FOREIGN KEY(binder_id,user_id) REFERENCES binders(id,user_id),
      CHECK(printing_id IS NOT NULL OR provisional_identity IS NOT NULL),
      UNIQUE(user_id,legacy_id));
    CREATE TABLE IF NOT EXISTS import_records(
      batch_id TEXT NOT NULL REFERENCES import_batches(id), legacy_id TEXT NOT NULL,
      printing_id TEXT NOT NULL REFERENCES printings(id), copy_id TEXT REFERENCES owned_copies(id),
      source_json TEXT NOT NULL, PRIMARY KEY(batch_id,legacy_id));
    CREATE TABLE IF NOT EXISTS private_archives(
      batch_id TEXT NOT NULL REFERENCES import_batches(id), user_id TEXT NOT NULL REFERENCES users(id),
      path TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL,
      PRIMARY KEY(batch_id,path));
    CREATE TABLE IF NOT EXISTS saved_hunts(
      batch_id TEXT NOT NULL REFERENCES import_batches(id), user_id TEXT NOT NULL REFERENCES users(id),
      legacy_id INTEGER NOT NULL, created TEXT, demo INTEGER, request TEXT, raw TEXT, coverage TEXT,
      PRIMARY KEY(batch_id,legacy_id));
    CREATE TABLE IF NOT EXISTS migration_issues(
      id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES import_batches(id),
      legacy_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS goal_templates(
      id TEXT PRIMARY KEY, game_id TEXT NOT NULL REFERENCES games(id), version TEXT NOT NULL,
      rules TEXT NOT NULL);
    """)
    return db
