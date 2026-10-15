"""Read-only state fingerprints shared by disposable qualification journeys.

Callers own root selection and synthetic-state guards. Keep the existing digest
shape stable so retained before/after evidence remains comparable across helpers.
"""

import hashlib
import json
import sqlite3


def persisted_snapshot(root):
    """Complete SQLite content plus independent protected file hashes; no writes."""
    databases = {}
    for path in sorted(root.rglob("*.db")):
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            schema = list(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
            tables = {}
            for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                quoted = '"' + name.replace('"', '""') + '"'
                rows = list(db.execute("SELECT * FROM " + quoted))
                normalized = [
                    [dict(blob_hex=value.hex()) if isinstance(value, bytes) else value for value in row]
                    for row in rows
                ]
                tables[name] = hashlib.sha256(
                    json.dumps(sorted(normalized, key=repr), sort_keys=True).encode()
                ).hexdigest()
            databases[str(path.relative_to(root))] = dict(
                schema_sha256=hashlib.sha256(json.dumps(schema).encode()).hexdigest(), tables=tables
            )
    files = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix != ".db" and not path.name.endswith(("-wal", "-shm", "-journal"))
    }
    return dict(databases=databases, protected_files=files)
