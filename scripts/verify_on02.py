"""Installed-package photo-batch journey with synthetic data and a fake CLI."""

import argparse
import hashlib
import io
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from PIL import Image, ImageDraw

PROJECT = Path(__file__).resolve().parents[1]
PREPARE = """
import sys,json,hashlib
from pathlib import Path
import pokemon_hunter
assert Path(pokemon_hunter.__file__).is_relative_to(Path(sys.prefix))
from pokemon_hunter.beta.cli import setup
setup(Path(sys.argv[1]))
from pokemon_hunter.beta import collection_drafts,photo_batches,store
from django.db import connection
collection_drafts.initialize()
def protected():
 return {t:hashlib.sha256(json.dumps(store.rows('SELECT * FROM '+t),sort_keys=True,default=str).encode()).hexdigest() for t in connection.introspection.table_names() if not t.startswith('scan_batch')}
before=protected();photo_batches.initialize();photo_batches.initialize();assert protected()==before
root=Path(sys.argv[1]);(root/'scan-config.json').write_text(json.dumps(dict(mode='codex_cli')))
print(json.dumps(dict(package_origin=str(Path(pokemon_hunter.__file__).resolve()),protected_tables=len(before),migration_additive_idempotent=True)))
"""
FAKE = """
import json,sys
from pathlib import Path
args=sys.argv[1:]
schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text())
if schema['title']=='Detection':
 payload=dict(schema_version='dex-detection-v1',status='proposed',boxes=[dict(x=.05,y=.1,width=.4,height=.8,rotation=0,issues=[]),dict(x=.55,y=.1,width=.4,height=.8,rotation=0,issues=[])])
else:
 prompt=args[-1];ids=json.loads(prompt.split('Images are in this exact crop-ID order: ')[1].split('. One record')[0])
 payload=dict(schema_version='dex-identities-v1',crops=[dict(crop_id=k,status='unreadable',name=None,set_name=None,number=None,language=None,edition=None,finish=None,variant=None,reason='Labeled engineering fixture: choose manually') for k in ids])
Path(args[args.index('-o')+1]).write_text(json.dumps(payload))
print(json.dumps(dict(type='turn.completed',usage=dict(input_tokens=20,output_tokens=5))))
"""


def run(args):
    from playwright.sync_api import expect, sync_playwright

    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = dict(
        status="FAIL",
        evidence_class="fresh wheel; disposable labeled engineering fixtures and fake CLI only",
        real_recognition_invocations=0,
        customer_uploads=0,
        spending=0,
        states=[],
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("DEX_", "EBAY_", "OPENAI_", "POKEMON_HUNTER_", "PYTHONPATH", "CODEX_"))
        and k != "DATABASE_URL"
    }
    env.update(
        DEX_PROFILE="local", PLAYWRIGHT_BROWSERS_PATH=str(Path.home() / "Library/Caches/ms-playwright")
    )
    with tempfile.TemporaryDirectory(prefix="dex-on02-engineering-") as tmp:
        tmp = Path(tmp)
        root = tmp / "synthetic"
        env["HOME"] = str(tmp)
        subprocess.run(
            [str(args.python), "-I", "-m", "pokemon_hunter.beta.synthetic", "--output", str(root)],
            env=env,
            cwd=tmp,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        prep = subprocess.check_output(
            [str(args.python), "-I", "-c", PREPARE, str(root)], env=env, cwd=tmp, text=True
        )
        report["migration"] = json.loads(prep)
        fake = tmp / "fake-on02-codex"
        fake.write_text(
            "#!"
            + str(args.python)
            + "\nimport time\nfrom pathlib import Path\nif Path("
            + repr(str(tmp / "fake-delay"))
            + ").exists():time.sleep(4)\n"
            + FAKE
        )
        fake.chmod(0o700)
        report["fake_sha256"] = hashlib.sha256(fake.read_bytes()).hexdigest()
        im = Image.new("RGB", (900, 650), "#183848")
        draw = ImageDraw.Draw(im)
        for x in (50, 500):
            draw.rectangle((x, 65, x + 350, 585), fill="#eee5c7")
            draw.text((x + 20, 100), "ENGINEERING FIXTURE\nNO REAL CARD ACCURACY", fill="black")
        photo = io.BytesIO()
        im.save(photo, "PNG")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        assert port != 8011
        base = f"http://127.0.0.1:{port}"
        with (out / "server.log").open("w") as log:
            server = subprocess.Popen(
                [
                    str(args.python),
                    "-I",
                    str(PROJECT / "scripts/serve_on02_engineering.py"),
                    "--root",
                    str(root),
                    "--fake",
                    str(fake),
                    "--output",
                    str(out),
                    "--port",
                    str(port),
                ],
                cwd=tmp,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
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
                    errors = []
                    external = []
                    requests = []

                    def route(r):
                        if r.request.url.startswith(base + "/"):
                            r.continue_()
                        else:
                            external.append(r.request.url)
                            r.abort()

                    context.route("**/*", route)
                    page = context.new_page()
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    context.on(
                        "request",
                        lambda r: requests.append(dict(method=r.method, path=r.url.removeprefix(base))),
                    )
                    page.goto(base + "/login/")
                    page.get_by_label("Username:", exact=True).fill("admin")
                    page.get_by_label("Password:", exact=True).fill(
                        json.loads((root / "credentials.json").read_text())["admin"]
                    )
                    page.get_by_role("button", name="Sign in", exact=True).click()
                    page.wait_for_url(lambda u: "/login/" not in u)
                    page.goto(base + "/add-photos/")
                    expect(page.locator("#photo-status")).to_contain_text("Start or resume")
                    page.locator("#photo-new").focus()
                    page.keyboard.press("Enter")
                    expect(page.locator("#photo-status")).to_contain_text("Empty photo batch")
                    page.locator("#photo-file").set_input_files(
                        dict(name="engineering.png", mimeType="image/png", buffer=photo.getvalue())
                    )
                    page.locator("#photo-upload").click()
                    expect(page.locator("#photo-status")).to_contain_text("staged locally")
                    batch_id = page.url.split("batch=")[1]
                    # Explicit consent is required; missing consent cannot dispatch.
                    page.get_by_role(
                        "button", name="Analyze overview for detection · photo 1", exact=True
                    ).click()
                    expect(page.locator("#photo-status")).to_contain_text("consent checkbox")
                    page.locator("#photo-consent").check()
                    page.get_by_role(
                        "button", name="Analyze overview for detection · photo 1", exact=True
                    ).click()
                    expect(page.get_by_text("Detection: proposed.", exact=False)).to_be_visible(timeout=15000)
                    page.get_by_role("button", name="Use proposed boxes for correction", exact=True).click()
                    expect(page.locator("fieldset")).to_have_count(2)
                    page.get_by_role(
                        "button", name="Confirm layout and count for photo 1", exact=True
                    ).click()
                    expect(page.locator(".photo-crop")).to_have_count(2)
                    page.locator("#photo-consent").check()
                    page.get_by_role(
                        "button", name="Analyze reviewed crops for identity · photo 1", exact=True
                    ).click()
                    expect(page.get_by_text("identity: completed", exact=False)).to_be_visible(timeout=15000)
                    (tmp / "fake-delay").touch()
                    page.locator("#photo-consent").check()
                    page.get_by_role(
                        "button", name="Analyze overview for detection · photo 1", exact=True
                    ).click()
                    expect(page.get_by_text("detection: processing", exact=False)).to_be_visible(
                        timeout=15000
                    )
                    page.locator("#photo-stop").click()
                    expect(page.locator("#photo-status")).to_contain_text("Stop recorded")
                    (tmp / "fake-delay").unlink()
                    catalog = page.request.get(base + "/api/bulk/catalog/").json()["groups"]
                    g = catalog[0]
                    printing = g["children"][0]["id"]
                    for i in range(2):
                        card = page.locator(".photo-crop").nth(i)
                        card.get_by_label("Find a catalog card · name, set or number", exact=True).fill(
                            g["name"]
                        )
                        card.get_by_label("Supported catalog printing", exact=True).select_option(printing)
                        card.get_by_label("Physical copy decision", exact=True).select_option("different")
                        card.get_by_label("Include this one physical card", exact=True).check()
                        if i == 0:
                            card.get_by_label(
                                "Retain this selected crop with its copy after Confirm", exact=True
                            ).check()
                        card.get_by_role("button", name="Save crop choice", exact=True).click()
                        expect(page.locator("#photo-status")).to_contain_text("choice saved")
                    # Layout and actual enlarged text, with font measurements per state.
                    for width in (1280, 390, 320):
                        for doubled in (False, True):
                            page.set_viewport_size(dict(width=width, height=900))
                            page.reload()
                            expect(page.locator(".photo-crop")).to_have_count(2)
                            before = page.locator("#photo-entry h1").evaluate(
                                "(e)=>parseFloat(getComputedStyle(e).fontSize)"
                            )
                            if doubled:
                                page.evaluate(
                                    "()=>{const nodes=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const [e,n]of nodes)e.style.fontSize=(2*n)+'px';}"
                                )
                            after = page.locator("#photo-entry h1").evaluate(
                                "(e)=>parseFloat(getComputedStyle(e).fontSize)"
                            )
                            assert after == before * (2 if doubled else 1)
                            assert not page.evaluate("document.documentElement.scrollWidth>innerWidth")
                            page.locator("#photo-stop").focus()
                            page.keyboard.press("Tab")
                            page.keyboard.press("Shift+Tab")
                            assert page.locator("#photo-stop").evaluate("(e)=>e===document.activeElement")
                            outline = page.locator("#photo-stop").evaluate(
                                "(e)=>({style:getComputedStyle(e).outlineStyle,width:parseFloat(getComputedStyle(e).outlineWidth)})"
                            )
                            assert outline["style"] != "none" and outline["width"] >= 2
                            page.screenshot(
                                path=str(out / f"engineering-{width}-{200 if doubled else 100}.png"),
                                full_page=True,
                            )
                            report["states"].append(
                                dict(
                                    width=width,
                                    text_percent=200 if doubled else 100,
                                    heading_before=before,
                                    heading_after=after,
                                    no_horizontal_overflow=True,
                                    keyboard_focus=outline,
                                )
                            )
                    page.set_viewport_size(dict(width=1280, height=900))
                    page.reload()
                    expect(page.locator(".photo-crop")).to_have_count(2)
                    page.locator("#photo-duplicates").check()
                    page.locator("#photo-handoff").click()
                    page.wait_for_url("**/add-many/?draft=*")
                    expect(page.locator("#bulk-tray")).to_contain_text(g["name"])
                    page.locator("#bulk-review").click()
                    expect(page.locator("#bulk-review-summary")).to_contain_text("2 new copies")
                    expect(page.locator("#bulk-confirm")).to_be_enabled()
                    page.locator("#bulk-confirm").click()
                    expect(page.locator("#bulk-receipt-body")).to_contain_text("This batch is saved")
                    expect(page.locator("#bulk-receipt-body")).to_contain_text("Photo batch")
                    page.reload()
                    expect(page.locator("#bulk-receipt-body")).to_contain_text("This batch is saved")
                    page.locator("#bulk-undo").click()
                    expect(page.locator("#bulk-receipt-body")).to_contain_text("undone")
                    report["checks"] = [
                        "upload without analysis",
                        "consent guard",
                        "fake detection subprocess",
                        "human crop/count review",
                        "fake identity subprocess",
                        "in-flight independent Stop through the HTTP/UI boundary",
                        "manual catalog corrections",
                        "same-printing different physical copies",
                        "explicit per-copy crop retention",
                        "ON-01 atomic Review/Confirm",
                        "receipt replay",
                        "Undo",
                        "keyboard entry and independent Stop focus",
                        "six viewport/text states",
                    ]
                    page.goto(base + "/add-photos/")
                    expect(page.locator("#photo-status")).to_contain_text("Start or resume")
                    page.locator("#photo-new").click()
                    expect(page.locator("#photo-status")).to_contain_text("Empty photo batch")
                    fresh = io.BytesIO()
                    im.resize((901, 650)).save(fresh, "PNG")
                    page.locator("#photo-file").set_input_files(
                        dict(name="engineering-authority.png", mimeType="image/png", buffer=fresh.getvalue())
                    )
                    page.locator("#photo-upload").click()
                    expect(page.locator(".photo-source img")).to_be_visible()
                    page.evaluate("window.discardNavigationAuthority(false)")
                    expect(page.locator("#photo-entry")).to_contain_text("session changed")
                    assert page.locator("#photo-entry img").count() == 0
                    report["checks"].append(
                        "shared authority-revoked event discards private photo DOM and late responses"
                    )
                    report["browser_errors"] = errors
                    report["external_requests"] = external
                    assert not errors and not external
                    report["local_storage"] = page.evaluate("Object.keys(localStorage)")
                    assert not report["local_storage"]
                    browser.close()
                report["provider_calls"] = json.loads((out / "provider-calls.json").read_text())
                assert report["provider_calls"]["calls"] == 0
                report["batch_id"] = batch_id
                report["status"] = "PASS"
            finally:
                if report["status"] != "PASS" and "page" in locals():
                    try:
                        page.screenshot(path=str(out / "failure.png"), full_page=True)
                        (out / "failure.html").write_text(page.content())
                    except Exception:
                        pass
                server.terminate()
                try:
                    server.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
                report["server_exit"] = server.returncode
                (out / "report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--python", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(p.parse_args()), indent=2))
