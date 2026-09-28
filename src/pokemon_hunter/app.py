"""Local collection application. Live discovery is an explicit user action."""

import json
import os
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictBool

from .collection import read, totals, update_card
from .config import load_config, load_env
from .ebay import EbayClient, discover
from .hunt import analyze, load_json, public_listing, query_plan
from .valuation import valuation


class Ownership(BaseModel):
    model_config = {"extra": "forbid"}
    owned: StrictBool
    first_edition: StrictBool = False


class SearchRequest(BaseModel):
    pool: Literal["singles", "known_lots", "mystery"] = "known_lots"
    focus: Literal["all", "kanto", "johto", "rares", "bulk"] = "all"
    budget: Decimal = Field(default=Decimal("150"), ge=0, le=10000)
    demo: bool = True
    offset: int = Field(default=0, ge=0)


def create_app(root: Path):
    app = FastAPI(title="Vintage 251", docs_url=None, redoc_url=None)
    collection_path = root / "config/pokedex_251.json"
    (root / "data").mkdir(exist_ok=True)
    db_path = root / "data/collection_hunts.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS hunts (id INTEGER PRIMARY KEY, created TEXT, demo INTEGER, request TEXT, raw TEXT, coverage TEXT)"
        )

    def collection():
        return read(collection_path)

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        # Local file mutations cannot be initiated by a different web origin.
        host = request.headers.get("host", "").split(":")[0]
        origin = request.headers.get("origin")
        if host not in ("127.0.0.1", "localhost", "testserver") or (
            origin and origin != f"http://{request.headers.get('host')}"
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse({"detail": "This app accepts local requests only"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/collection")
    def get_collection():
        data = collection()
        return {
            **data,
            "totals": totals(data),
            "valuation": valuation(data, root / "config/market_values.json"),
        }

    @app.put("/api/cards/{card_id}")
    def put_card(card_id: str, body: Ownership):
        try:
            data = update_card(collection_path, card_id, body.owned, body.first_edition)
        except ValueError as exc:
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
        data = collection()
        config = load_json(root / "config/hunt.json")
        values = load_json(root / "config/raw_values.json")
        results = [analyze(r, data, config, values, demo=demo) for r in raws]
        results = [
            r
            for r in results
            if r["active"]
            and r["delivered"] is not None
            and Decimal(r["delivered"]) <= body.budget
            and r["pool"] == body.pool
        ]
        if body.pool == "singles":
            results = [r for r in results if r["dex_hits"]]
        if body.focus in ("kanto", "johto"):
            results = [r for r in results if r[f"{body.focus}_hits"] or not r["cards"]]
        if body.focus == "rares":
            results = [r for r in results if r["has_rare"] or not r["cards"]]
        if body.focus == "bulk":
            results = [r for r in results if r["count"] and r["count"] >= 25]
        for row in results:
            if row["max_bid"] is not None:
                row["max_bid"] = str(
                    max(Decimal(0), min(Decimal(row["max_bid"]), body.budget - Decimal(row["shipping"])))
                )
        return sorted(results, key=lambda r: (r["score"] is not None, r["score"] or 0), reverse=True)

    @app.post("/api/hunts")
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
            except RuntimeError as exc:
                raise HTTPException(502, str(exc)) from None
            finally:
                client.close()
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
