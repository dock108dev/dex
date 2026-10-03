"""Local collection application. Live discovery is an explicit user action."""

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StrictBool

from . import hunt
from .beta.diagnostics import closing, failure
from .collection import CollectionInputError, read, totals, update_card
from .config import load_config, load_env
from .ebay import EbayClient, EbayError, discover
from .hunt import SearchRequest, load_json, public_listing, query_plan
from .security import BROWSER_HEADERS, loopback_authority
from .valuation import valuation


class Ownership(BaseModel):
    model_config = {"extra": "forbid"}
    owned: StrictBool
    first_edition: StrictBool = False


def require_json(request: Request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "Send an application/json request")


def create_app(root: Path):
    app = FastAPI(title="Vintage 251", docs_url=None, redoc_url=None)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # FastAPI's default validation response includes submitted field values.
        return JSONResponse({"detail": "Invalid request fields"}, status_code=422, headers=BROWSER_HEADERS)

    collection_path = root / "config/pokedex_251.json"
    (root / "data").mkdir(exist_ok=True)
    db_path = root / "data/collection_hunts.db"
    if db_path.is_symlink():
        raise OSError("Hunt storage requires a regular destination, not a symlink")
    if not db_path.exists():
        # SQLite otherwise creates new files using the caller's umask (often 022).
        fd = os.open(db_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS hunts (id INTEGER PRIMARY KEY, created TEXT, demo INTEGER, request TEXT, raw TEXT, coverage TEXT)"
        )

    def collection():
        return read(collection_path)

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # Local file mutations cannot be initiated by a different web origin.
        hosts = request.headers.getlist("host")
        host = hosts[0] if len(hosts) == 1 else ""
        origin = request.headers.get("origin")
        if (
            not loopback_authority(host)
            or request.client is None
            or request.client.host not in {"127.0.0.1", "::1"}
            or any(k == "forwarded" or k.startswith("x-forwarded-") for k in request.headers)
            or (origin and origin != f"http://{host}")
        ):
            return JSONResponse(
                {"detail": "This app accepts local requests only"}, status_code=403, headers=BROWSER_HEADERS
            )
        try:
            response = await call_next(request)
        except Exception as exc:
            # Handle here so the ASGI server does not log a raw traceback after a 500.
            failure("legacy_request_failed", exc)
            response = JSONResponse(
                {
                    "detail": "Request failed. Check saved state before retrying; inspect the server diagnostics."
                },
                status_code=500,
            )
        response.headers.update(BROWSER_HEADERS)
        return response

    @app.get("/api/collection")
    def get_collection():
        data = collection()
        return {
            **data,
            "totals": totals(data),
            "valuation": valuation(data, root / "config/market_values.json"),
        }

    @app.put("/api/cards/{card_id}", dependencies=[Depends(require_json)])
    def put_card(card_id: str, body: Ownership):
        try:
            data = update_card(collection_path, card_id, body.owned, body.first_edition)
        except CollectionInputError as exc:
            raise HTTPException(400, str(exc)) from None
        return {"totals": totals(data)}

    @app.get("/api/export")
    def export():
        return FileResponse(collection_path, filename="pokedex_251.json", media_type="application/json")

    @app.get("/api/status")
    def status():
        load_env(root / ".env")
        return {
            "live_configured": bool(os.getenv("EBAY_CLIENT_ID") and os.getenv("EBAY_CLIENT_SECRET")),
            "value_records": len(load_json(root / "config/raw_values.json")),
        }

    def project_results(raws, body, demo):
        return hunt.project_results(
            raws,
            body,
            demo,
            collection(),
            load_json(root / "config/hunt.json"),
            load_json(root / "config/raw_values.json"),
        )

    @app.post("/api/hunts", dependencies=[Depends(require_json)])
    def search(body: SearchRequest):
        data = collection()
        config = load_json(root / "config/hunt.json")
        plan = query_plan(data, config, body.pool, body.focus)
        queries = plan[body.offset : body.offset + config["query_limit"]]
        if body.demo:
            raw = load_json(root / "config/demo_hunts.json")
            coverage = {
                "note": "Synthetic examples, not live offers. Scored against your current recorded collection.",
                "queries_run": 0,
                "queries_total": len(plan),
                "next_offset": None,
            }
        else:
            load_env(root / ".env")
            settings, _, _ = load_config(root)
            client = EbayClient(settings)
            try:
                with closing(client, "legacy_ebay_client_close_failed"):
                    raw = discover(client, queries)
                coverage = {
                    "note": "Bounded eBay search; seller text only. Photos have not been analyzed. Check availability on eBay.",
                    "queries_run": len(queries),
                    "queries_total": len(plan),
                    "next_offset": body.offset + len(queries)
                    if body.offset + len(queries) < len(plan)
                    else None,
                    "warnings": ["Search coverage was limited by a page cap or API warning."]
                    if client.warnings
                    else [],
                }
            except EbayError as exc:
                failure("legacy_ebay_search_failed", exc)
                raise HTTPException(
                    502, "eBay search failed. Check credentials, access and connection before retrying."
                ) from None
        rows = project_results(raw, body, body.demo)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO hunts(created,demo,request,raw,coverage) VALUES(?,?,?,?,?)",
                (
                    datetime.now(UTC).isoformat(),
                    body.demo,
                    body.model_dump_json(),
                    json.dumps(raw),
                    json.dumps(coverage),
                ),
            )
            hunt_id = cursor.lastrowid
        return {
            "hunt_id": hunt_id,
            "coverage": coverage,
            "results": [public_listing(r) for r in rows],
            "demo": body.demo,
        }

    def stored(hunt_id):
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT request, raw, coverage, demo FROM hunts WHERE id=?", (hunt_id,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "Hunt not found")
        return row

    @app.get("/api/hunts")
    def history():
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT id,created,demo,request FROM hunts ORDER BY id DESC LIMIT 30"
            ).fetchall()
        return [
            {"id": r[0], "created": r[1], "demo": bool(r[2]), "pool": json.loads(r[3])["pool"]} for r in rows
        ]

    @app.get("/api/hunts/{hunt_id}")
    def saved(hunt_id: int):
        req, raw, coverage, demo = stored(hunt_id)
        rows = project_results(json.loads(raw), SearchRequest.model_validate_json(req), bool(demo))
        return {
            "hunt_id": hunt_id,
            "results": [public_listing(r) for r in rows],
            "coverage": json.loads(coverage),
            "demo": bool(demo),
        }

    @app.post("/api/hunts/{hunt_id}/reveal/{item_id:path}")
    def reveal(hunt_id: int, item_id: str):
        req, raw, _, demo = stored(hunt_id)
        rows = project_results(json.loads(raw), SearchRequest.model_validate_json(req), bool(demo))
        row = next((r for r in rows if r["id"] == item_id), None)
        if not row:
            raise HTTPException(404, "Listing no longer fits this hunt")
        return public_listing(row, reveal=True)

    @app.get("/")
    def home():
        return FileResponse(root / "web/index.html")

    app.mount("/static", StaticFiles(directory=root / "web"), name="static")
    return app


def serve(root: Path, port=8765):
    import uvicorn

    uvicorn.run(create_app(root), host="127.0.0.1", port=port)
