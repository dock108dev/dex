"""Installed-package bulk-entry browser checks using disposable state."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.ci.browser import browser_cache  # noqa: E402

PREPARE = r"""
import hashlib,json,sys,sqlite3
from pathlib import Path
import pokemon_hunter
package=Path(pokemon_hunter.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix).resolve())
root=Path(sys.argv[1]);metadata=json.loads(Path(sys.argv[2]).read_text())
from pokemon_hunter.beta.cli import setup
setup(root)
from pokemon_hunter.beta import collection_drafts,collection,store
from django.contrib.auth import get_user_model
from django.db import connection
owner=store.principal(get_user_model().objects.get(username='admin').pk)
# Engineering fixture seeds only public catalog metadata, with original IDs. No customer records.
with connection.cursor() as cursor:
    for table,rows in metadata.items():
        for row in rows:
            keys=list(row)
            pk=('provider','entity_kind','external_id') if table=='external_mappings' else ('game','language','alias') if table=='catalog_aliases' else ('id',)
            mutable=[k for k in keys if k not in pk]
            cursor.execute('INSERT INTO '+table+' ('+','.join(keys)+') VALUES ('+','.join(['%s']*len(keys))+') ON CONFLICT ('+','.join(pk)+') DO UPDATE SET '+','.join(k+'=excluded.'+k for k in mutable),list(row.values()))
def protected():
    names=[t for t in connection.introspection.table_names() if not t.startswith('collection_draft') and t!='collection_replays']
    result={}
    for t in names:
        rows=store.rows('SELECT * FROM '+t)
        result[t]=hashlib.sha256(json.dumps(sorted([json.dumps(r,sort_keys=True,default=str) for r in rows])).encode()).hexdigest()
    return result
before=protected();collection_drafts.initialize();collection_drafts.initialize();assert protected()==before
from pokemon_hunter.beta import bulk_input
entries=collection.catalog(owner)
# Finite normalization probes, without any inventory writes or implicit catalog variants.
validated=0
for offset in range(0,len(entries),2000):
    rows=[dict(row_id='catalog-'+p['id'],printing_id=p['id'],duplicate_decision='different') for p in entries[offset:offset+2000]]
    normalized=bulk_input.normalize(owner,bulk_input.envelope(dict(rows=rows)))
    assert all(not r['errors'] for r in normalized['rows']), [r for r in normalized['rows'] if r['errors']][:2]
    assert [r['printing_id'] for r in normalized['rows']]==[p['id'] for p in entries[offset:offset+2000]]
    validated+=len(rows)
# Real metadata edge cases stay unresolved or fail; no guessed combinations.
def probe(set_name,number,**kw):
    rows=[dict(row_id='edge',set=set_name,number=number,**kw)]
    return bulk_input.normalize(owner,bulk_input.envelope(dict(rows=rows)))['rows'][0]
assert probe('Base Set 2','2',edition='first_edition')['errors']
assert probe('Base Set','2',edition='shadowless')['errors']
assert probe('Prismatic Evolutions','001',finish='reverse')['errors']
assert not probe('Prismatic Evolutions','001',finish='reverse',keep_unknown=True)['errors']
assert probe('Scarlet & Violet—151','001/999')['errors']
assert probe('Scarlet & Violet—151','001',keep_unknown=True)['matched_number']=='001/165'
assert protected()==before
print(json.dumps(dict(package_origin=str(package),migration_additive_and_idempotent=True,protected_tables=len(before),catalog_printings=len(entries),catalog_sets=len({p['set_id'] for p in entries}),validated_printing_combinations=validated,metadata_edge_cases=6)))
"""


def main(args):
    from playwright.sync_api import expect, sync_playwright

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = dict(
        status="FAIL",
        evidence_class="installed disposable engineering accounts with current public catalog metadata; no customer experience",
        provider_operations=0,
        timings={},
        checks=[],
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("DEX_", "EBAY_", "OPENAI_", "POKEMON_HUNTER_", "PYTHONPATH"))
        and k != "DATABASE_URL"
    }
    env.update(DEX_PROFILE="local", PLAYWRIGHT_BROWSERS_PATH=str(browser_cache()))
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="dex-on01-engineering-") as tmp:
        tmp = Path(tmp)
        root = tmp / "synthetic"
        env["HOME"] = str(tmp)
        subprocess.run(
            [str(args.python), "-I", "-m", "pokemon_hunter.beta.synthetic", "--output", str(root)],
            env=env,
            check=True,
            cwd=tmp,
            stdout=subprocess.DEVNULL,
        )
        preparation = subprocess.run(
            [str(args.python), "-I", "-c", PREPARE, str(root), str(args.metadata.resolve())],
            env=env,
            check=True,
            cwd=tmp,
            text=True,
            capture_output=True,
        )
        report["migration"] = json.loads(preparation.stdout)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        assert port != 8011
        base = f"http://127.0.0.1:{port}"
        with (output / "server.log").open("w") as log:
            server = subprocess.Popen(
                [
                    str(args.python),
                    "-I",
                    str(PROJECT / "scripts/serve_e4a.py"),
                    "--root",
                    str(root),
                    "--output",
                    str(output),
                    "--port",
                    str(port),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=tmp,
            )
            try:
                for _ in range(100):
                    try:
                        if urlopen(base + "/login/", timeout=1).status == 200:
                            break
                    except OSError:
                        time.sleep(0.1)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    context = browser.new_context(viewport=dict(width=1280, height=900))
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    context.route(
                        "**/*",
                        lambda r: (
                            r.continue_()
                            if r.request.url.startswith(base + "/")
                            else r.fulfill(status=404, body="Engineering remote asset blocked")
                        ),
                    )
                    page.goto(base + "/login/")
                    page.get_by_label("Username:", exact=True).fill("admin")
                    page.get_by_label("Password:", exact=True).fill(
                        json.loads((root / "credentials.json").read_text())["admin"]
                    )
                    page.get_by_role("button", name="Sign in", exact=True).click()
                    t = time.monotonic()
                    page.goto(base + "/add-many/")
                    expect(page.locator("#bulk-status")).to_contain_text("Select cards")
                    report["timings"]["initial_catalog_seconds"] = round(time.monotonic() - t, 3)
                    catalog = page.request.get(base + "/api/bulk/catalog/").json()
                    assert len(catalog["sets"]) >= 68 and len(catalog["groups"]) >= 4275
                    base2 = next(s for s in catalog["sets"] if s["name"] == "Base Set 2")
                    page.locator("#bulk-set").select_option(base2["id"])
                    expect(page.locator("#bulk-catalog-rows .bulk-card")).to_have_count(50)
                    t = time.monotonic()
                    first = page.locator("#bulk-catalog-rows input").first
                    first.focus()
                    page.keyboard.press("Space")
                    page.locator("#bulk-catalog-rows input").last.check()
                    page.locator("#bulk-range").click()
                    expect(page.locator("#bulk-count")).to_contain_text("50 draft rows")
                    report["timings"]["keyboard_and_range_50_seconds"] = round(time.monotonic() - t, 3)
                    page.locator("#bulk-tray button").first.click()
                    expect(page.locator("#bulk-drawer")).to_be_visible()
                    page.locator("#bulk-row-action").select_option("mark_owned")
                    expect(page.locator("#bulk-row-condition")).to_be_disabled()
                    page.locator("#bulk-row-action").select_option("add_copies")
                    page.locator("#bulk-row-notes").fill("Engineering row exception")
                    page.locator("#bulk-row-save").click()
                    expect(page.locator("#bulk-tray button").first).to_be_focused()
                    report["drawer_focus_return"] = True
                    t = time.monotonic()
                    page.locator("#bulk-all").click()
                    expect(page.locator("#bulk-count")).to_contain_text("130 draft rows")
                    report["timings"]["select_all_130_seconds"] = round(time.monotonic() - t, 3)
                    page.locator("#bulk-search").fill("No card matches")
                    expect(page.locator("#bulk-count")).to_contain_text("130 hidden")
                    page.locator("#bulk-search").fill("")
                    page.locator("#bulk-check-all").click()
                    page.locator("#bulk-unknown").click()
                    page.locator("#bulk-review").click()
                    expect(page.locator("#bulk-review-summary")).to_contain_text(
                        "130 new copies", timeout=30000
                    )
                    expect(page.locator("#bulk-confirm")).to_be_enabled()
                    report["checks"].append(
                        "current catalog, keyboard/range selection, 50 visible rows, explicit all matching, hidden selections and group-bound variant multi-edit"
                    )
                    for width in (1280, 390, 320):
                        for doubled in (False, True):
                            page.set_viewport_size(dict(width=width, height=900))
                            if doubled:
                                measured = page.evaluate(
                                    """() => {const nodes=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);const target=document.querySelector('#bulk-confirm'),before=parseFloat(getComputedStyle(target).fontSize);nodes.forEach(([e,n])=>e.style.fontSize=(2*n)+'px');return [before,parseFloat(getComputedStyle(target).fontSize)];}"""
                                )
                                assert measured[1] == measured[0] * 2
                                report.setdefault("text_measurements", []).append(
                                    dict(width=width, before=measured[0], actual=measured[1])
                                )
                            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                            page.screenshot(
                                path=str(output / f"engineering-review-{width}-{doubled}.png"), full_page=True
                            )
                            page.locator("#bulk-review-panel").evaluate(
                                "e=>e.scrollIntoView({block:'start'})"
                            )
                            page.screenshot(
                                path=str(output / f"engineering-review-viewport-{width}-{doubled}.png")
                            )
                            if doubled:
                                page.evaluate(
                                    "document.querySelectorAll('body,body *').forEach(e=>e.style.removeProperty('font-size'))"
                                )
                    page.set_viewport_size(dict(width=1280, height=900))
                    t = time.monotonic()
                    page.locator("#bulk-confirm").click()
                    expect(page.locator("#bulk-receipt")).to_be_visible(timeout=30000)
                    report["timings"]["confirm_130_seconds"] = round(time.monotonic() - t, 3)
                    receipt = page.locator("#bulk-receipt-body").inner_text()
                    page.reload()
                    expect(page.locator("#bulk-receipt")).to_be_visible()
                    assert page.locator("#bulk-receipt-body").inner_text() == receipt
                    page.locator("#bulk-recover").click()
                    expect(page.locator("#bulk-receipt")).to_be_visible()
                    receipt_url = page.url
                    # Group-bound records participate in the ordinary editor; opening/cancelling is read-only.
                    card_url = page.locator("#bulk-receipt-body a").first.get_attribute("href")
                    page.goto(base + card_url)
                    expect(page.locator("#group-copies .card-copy-row").first).to_be_visible()
                    page.locator("#group-copies .copy-actions summary").first.click()
                    page.locator("[data-group-resolve]").first.click()
                    expect(page.locator("#group-resolve-child")).to_be_visible()
                    page.keyboard.press("Escape")
                    page.goto(receipt_url)
                    expect(page.locator("#bulk-receipt")).to_be_visible()
                    # A server restart loses no draft, operation or receipt identity.
                    server.terminate()
                    server.wait(timeout=10)
                    server = subprocess.Popen(
                        [
                            str(args.python),
                            "-I",
                            str(PROJECT / "scripts/serve_e4a.py"),
                            "--root",
                            str(root),
                            "--output",
                            str(output),
                            "--port",
                            str(port),
                        ],
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        cwd=tmp,
                    )
                    for _ in range(100):
                        try:
                            if urlopen(base + "/login/", timeout=1).status == 200:
                                break
                        except OSError:
                            time.sleep(0.1)
                    page.reload()
                    expect(page.locator("#bulk-receipt")).to_be_visible()
                    assert page.locator("#bulk-receipt-body").inner_text() == receipt
                    report["restart_recovery"] = True
                    page.locator("#bulk-undo").click()
                    expect(page.locator("#bulk-status")).to_contain_text("Whole batch undone", timeout=30000)
                    report["checks"].append(
                        "atomic checklist confirmation, persisted reload/network recovery and whole-batch undo; six normal/actual doubled-text layouts without overflow"
                    )
                    # Ordinary paste and mixed-set CSV use the same shared draft/review pipeline.
                    page.locator("#bulk-new").click()
                    page.locator("[data-input=paste]").click()
                    page.locator("#bulk-paste-text").fill("001-003 x2")
                    t = time.monotonic()
                    page.locator("#bulk-parse-paste").click()
                    expect(page.locator("#bulk-count")).to_contain_text("3 draft rows")
                    page.locator("#bulk-review").click()
                    expect(page.locator("#bulk-review-summary")).to_contain_text(
                        "6 new copies", timeout=30000
                    )
                    report["timings"]["paste_review_seconds"] = round(time.monotonic() - t, 3)
                    page.locator("#bulk-back-edit").click()
                    jungle = next(s for s in catalog["sets"] if s["name"] == "Jungle")
                    jungle_group = next(g for g in catalog["groups"] if g["set_id"] == jungle["id"])
                    page.locator("#bulk-set").select_option(jungle["id"])
                    page.locator("#bulk-paste-text").fill(jungle_group["collector_number"])
                    page.locator("#bulk-parse-paste").click()
                    expect(page.locator("#bulk-count")).to_contain_text("4 draft rows")
                    page.locator("#bulk-review").click()
                    expect(page.locator("#bulk-review-summary")).to_contain_text("7 new copies")
                    report["mixed_set_paste_append"] = True
                    page.locator("#bulk-back-edit").click()
                    page.locator("#bulk-cancel").click()
                    expect(page.locator("#bulk-status")).to_contain_text("Draft cancelled")
                    page.locator("#bulk-new").click()
                    page.locator("[data-input=csv]").click()
                    page.locator("#bulk-file").set_input_files(
                        dict(name="bad-utf8.csv", mimeType="text/csv", buffer=b"\xff")
                    )
                    page.locator("#bulk-parse-csv").click()
                    expect(page.locator("#bulk-status")).to_contain_text("valid UTF-8")
                    report["malformed_utf8_retained"] = True
                    groups = [g for g in catalog["groups"] if g["set_id"] == base2["id"]]
                    printing = groups[0]["children"][0]["id"]
                    text = "schema,row_id,action,printing_id,quantity,notes\n" + "".join(
                        f"dex-onboarding-v1,large-{i},add_copies,{printing},1,{('n' * 650)}\n"
                        for i in range(2000)
                    )
                    assert 1_400_000 < len(text.encode()) <= 1_500_000
                    report["csv_bytes"] = len(text.encode())
                    page.locator("#bulk-file").set_input_files(
                        dict(name="engineering-2000.csv", mimeType="text/csv", buffer=text.encode())
                    )
                    t = time.monotonic()
                    page.locator("#bulk-parse-csv").click()
                    expect(page.locator("#bulk-count")).to_contain_text("2000 draft rows", timeout=30000)
                    assert page.locator("#bulk-tray .bulk-draft-row").count() == 50
                    page.locator("#bulk-check-all").click()
                    page.locator("#bulk-different").click()
                    page.locator("#bulk-review").click()
                    expect(page.locator("#bulk-review-summary")).to_contain_text(
                        "2000 new copies", timeout=60000
                    )
                    expect(page.locator("#bulk-confirm")).to_be_enabled()
                    report["timings"]["load_and_review_2000_seconds"] = round(time.monotonic() - t, 3)
                    t = time.monotonic()
                    page.locator("#bulk-confirm").click()
                    expect(page.locator("#bulk-receipt")).to_be_visible(timeout=60000)
                    report["timings"]["confirm_2000_seconds"] = round(time.monotonic() - t, 3)
                    page.reload()
                    expect(page.locator("#bulk-receipt")).to_be_visible(timeout=30000)
                    page.screenshot(path=str(output / "engineering-2000-receipt.png"), full_page=True)
                    saved_large_url = page.url
                    # Real ASGI stream: valid manual JSON can exceed the ordinary request cap.
                    generation_before = page.request.get(base + "/api/collection-context/").json()[
                        "effective_collection"
                    ]["generation"]
                    large_input = dict(
                        input=dict(
                            rows=[
                                dict(
                                    row_id="large-note-" + str(i),
                                    printing_id=printing,
                                    notes="n" * 1000,
                                    duplicate_decision="different",
                                )
                                for i in range(2000)
                            ]
                        ),
                        new_batch=True,
                        batch_identity=str(uuid.uuid4()),
                    )
                    encoded = json.dumps(large_input)
                    assert len(encoded.encode()) > 2_000_000
                    csrf = next(c["value"] for c in context.cookies() if c["name"] == "dex_b1_csrf")
                    t = time.monotonic()
                    response = page.request.post(
                        base + "/api/bulk/save/",
                        data=encoded,
                        headers={"Content-Type": "application/json", "X-CSRFToken": csrf},
                    )
                    assert response.status == 200, response.status
                    large = response.json()["draft"]
                    assert len(large["input_json"]["rows"]) == 2000
                    report["timings"]["large_json_save_seconds"] = round(time.monotonic() - t, 3)
                    report["manual_json_bytes"] = len(encoded.encode())
                    cancelled = page.request.post(
                        base + "/api/bulk/drafts/" + large["id"] + "/cancel/",
                        data=json.dumps(dict(revision=large["revision"])),
                        headers={"Content-Type": "application/json", "X-CSRFToken": csrf},
                    )
                    assert cancelled.status == 200
                    assert (
                        page.request.get(base + "/api/collection-context/").json()["effective_collection"][
                            "generation"
                        ]
                        == generation_before
                    )
                    # Repeat a large review with 2,000 matching existing records. Counts stay compact.
                    page.locator("#bulk-new").click()
                    page.locator("[data-input=csv]").click()
                    page.locator("#bulk-file").set_input_files(
                        dict(name="engineering-new-2000.csv", mimeType="text/csv", buffer=text.encode())
                    )
                    t = time.monotonic()
                    page.locator("#bulk-parse-csv").click()
                    expect(page.locator("#bulk-count")).to_contain_text("2000 draft rows", timeout=30000)
                    page.locator("#bulk-check-all").click()
                    page.locator("#bulk-different").click()
                    page.locator("#bulk-review").click()
                    expect(page.locator("#bulk-review-summary")).to_contain_text(
                        "2000 new copies", timeout=60000
                    )
                    expect(page.locator("#bulk-review-rows")).to_contain_text("2000 current / 2000 recorded")
                    report["timings"]["review_2000_with_2000_existing_seconds"] = round(
                        time.monotonic() - t, 3
                    )
                    page.locator("#bulk-cancel").click()
                    expect(page.locator("#bulk-status")).to_contain_text("Draft cancelled")
                    page.goto(saved_large_url)
                    expect(page.locator("#bulk-receipt")).to_be_visible()
                    page.locator("#bulk-undo").click()
                    expect(page.locator("#bulk-status")).to_contain_text("Whole batch undone", timeout=60000)
                    report["checks"].append(
                        "2,000 CSV source/normalized/expanded rows, selected-row duplicate acknowledgement, 50 visible draft/review rows, atomic confirm, receipt recovery and atomic undo"
                    )
                    # One stale tab cannot cancel or confirm a revised draft.
                    page.locator("#bulk-new").click()
                    page.locator("[data-input=checklist]").click()
                    page.locator("#bulk-catalog-rows input").first.check()
                    page.locator("#bulk-save").click()
                    expect(page.locator("#bulk-status")).to_contain_text("Draft saved")
                    stale = page.url
                    other = context.new_page()
                    other.goto(stale)
                    expect(other.locator("#bulk-count")).to_contain_text("1 draft rows")
                    page.locator("#bulk-quantity").fill("2")
                    page.locator("#bulk-save").click()
                    expect(page.locator("#bulk-status")).to_contain_text("revision 2")
                    other.locator("#bulk-cancel").click()
                    expect(other.locator("#bulk-status")).to_contain_text("changed")
                    other.close()
                    page.reload()
                    expect(page.locator("#bulk-count")).to_contain_text("1 draft rows")
                    page.locator("#bulk-cancel").click()
                    expect(page.locator("#bulk-status")).to_contain_text("Draft cancelled")
                    report["checks"].append(
                        "multiple-tab CAS rejects stale cancellation and reload resumes exact revision without collection writes"
                    )
                    assert not errors, errors
                    report["browser_errors"] = errors
                    report["status"] = "PASS"
                    context.close()
                    browser.close()
            except Exception:
                report["failure"] = traceback.format_exc()
                raise
            finally:
                server.terminate()
                server.wait(timeout=10)
                report["provider_operations"] = json.loads((output / "provider-calls.json").read_text())[
                    "calls"
                ]
                report["duration_seconds"] = round(time.monotonic() - started, 3)
                (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--python", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.python = a.python.absolute()
    main(a)
