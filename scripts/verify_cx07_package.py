"""Verify navigation and contextual Shopping from a fresh offline locked wheel and execute its installed UI.

The runtime runs only from a new isolated installed environment. Chromium signs
in ordinarily and executes the installed modules against disposable engineering
state. External requests are controlled; the customer installation is untouched.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path
from urllib.request import urlopen

from verify_cx02 import free_port
from verify_cx04_package import REQUIRED as PREVIOUS_REQUIRED

PROJECT = Path(__file__).resolve().parents[1]
REQUIRED = (
    *PREVIOUS_REQUIRED,
    "pokemon_hunter/beta/navigation.py",
    "pokemon_hunter/beta/shopping_context.py",
    "pokemon_hunter/beta/static/navigation.js",
    "pokemon_hunter/beta/shopping_views.py",
    "pokemon_hunter/beta/static/lot_calculator.js",
    "pokemon_hunter/beta/static/lot_calculator.css",
    "pokemon_hunter/beta/templates/beta/lot_calculator.html",
    "pokemon_hunter/beta/settings.py",
    "pokemon_hunter/beta/static/card-screens.js",
    "pokemon_hunter/beta/static/species-screens.js",
    "pokemon_hunter/beta/static/public-species.js",
    "pokemon_hunter/beta/static/public.css",
    "pokemon_hunter/beta/templates/beta/public_pokedex.html",
    "pokemon_hunter/beta/templates/beta/public_species.html",
    "pokemon_hunter/beta/templates/beta/species_error.html",
    "pokemon_hunter/beta/species_projection.py",
    "pokemon_hunter/beta/species_views.py",
    "pokemon_hunter/beta/templates/beta/header.html",
    "pokemon_hunter/beta/templates/beta/base.html",
    "pokemon_hunter/beta/collection_intents.py",
    "pokemon_hunter/beta/effective_collection.py",
)
ORIGIN_CHECK = """
import hashlib, json, os, socket, sys
from pathlib import Path
expected=json.loads(sys.argv[1]); work=Path(sys.argv[2]); scripts=sys.argv[3]
os.environ['DEX_PROFILE']='local'
import pokemon_hunter
package=Path(pokemon_hunter.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix).resolve()), package
assert package.parent.name != 'src', package
for name, digest in expected.items():
    assert hashlib.sha256((package.parent/name).read_bytes()).hexdigest()==digest, name
sys.path.insert(0,scripts)
"""
PROBE = (
    ORIGIN_CHECK
    + """
def prohibit(*args, **kwargs):
    raise AssertionError('Installed read-only probe forbids network/provider requests')
socket.socket.connect=prohibit
socket.socket.connect_ex=prohibit
from verify_cx05 import prepare, persisted_snapshot
root=work/'engineering-root'; fixture_path=work/'fixture.json'
prepare(root,work/'source',fixture_path)
fixture=json.loads(fixture_path.read_text())
from pokemon_hunter.beta import collection, store
# This disposable fixture is synthetic; preserve aliases while declaring the
# existing staging-allowed synthetic provider instead of weakening stage policy.
for printing in store.rows('SELECT id,provenance FROM printings'):
    provenance=json.loads(printing['provenance'])
    provenance['provider']='dex-synthetic'
    collection.execute('UPDATE printings SET provenance=%s WHERE id=%s',
                       [json.dumps(provenance),printing['id']])
from django.test import Client
from django.conf import settings
from django.urls import clear_url_caches
from qualify_shopping import PASSWORD
from pokemon_hunter.beta import urls, image_mappings
import importlib
client=Client(HTTP_HOST='127.0.0.1:8011',REMOTE_ADDR='127.0.0.1')
assert client.get('/login/').status_code==200
signed=client.post('/login/',dict(username='admin',password=PASSWORD,
                  csrfmiddlewaretoken=client.cookies['dex_b1_csrf'].value))
assert signed.status_code==302, signed.content
before=persisted_snapshot(root)
owned=client.get('/api/my-card-groups/').json()
catalog=client.get('/api/card-groups/').json()
authority=client.get('/api/collection/').json()['effective_collection']
assert authority['generation']==owned['generation']==catalog['generation']
assert authority['user_id']==owned['account_id']==catalog['account_id']
species=client.get('/api/pokedex-species/').json()
assert len(species['species'])==251 and species['account_id']==authority['user_id']
assert species['generation']==authority['generation']
assert species['progress']['total']==251 and species['progress']['units']=='species'
assert all(row['present'] for row in owned['groups'])
group=next(row for row in owned['groups'] if row['name']=='Ivysaur' and row['collector_number']=='44')
base=next(row for row in owned['groups'] if row['name']=='Ivysaur' and row['collector_number']=='30')
assert group['id']!=base['id'] and base['established_total_quantity']==3
assert group['established_total_quantity'] is None
assert any(row['name']=='Mew' and row['collector_number']=='8' for row in catalog['groups'])
options=client.get('/api/card-group-filters/?scope=owned').json()
assert options['account_id']==owned['account_id']
assert any(row['name']=='Retained archive' for row in options['sets'])
assert len(image_mappings._reviewed()['species'])==251
assert len(image_mappings._reviewed()['cards'])==1086
path=group['url']
plain=client.get('/api/card-groups/'+group['id']+'/').json()
assert plain['selected_child'] is None and plain['selected_child_image'] is None
chosen=client.get('/api/card-groups/'+group['id']+'/?child='+fixture['selected_printing']).json()
assert chosen['selected_child_image']['availability']=='unavailable'
archived=client.get('/api/card-groups/'+group['id']+'/?child='+fixture['archived_printing']).json()
assert archived['selected_child']['available'] is False
assert 'account_id' not in client.get('/api/public/card-groups/').json()
assert client.get('/api/card-groups/'+group['id']+'/?child='+fixture['foreign_printing']).status_code==404
assert client.get('/cards/'+fixture['ambiguous_alias']+'/').status_code==409
legacy=client.get('/cards/'+fixture['selected_alias']+'/')
assert legacy.status_code==302 and legacy.url==path+'?child='+fixture['selected_printing']
assert client.get(path,dict(return_='/cards/')).status_code==400
assert client.get(path,{'return':'/cards/?page=2&scroll=840'}).status_code==200
assert client.get(path,{'return':'https://elsewhere.test/cards/'}).status_code==400
profiles=[]
old=(settings.PARITY_ENABLED,settings.STAGING)
try:
    for parity,staging in ((False,False),(True,False),(False,True),(True,True)):
        settings.PARITY_ENABLED,settings.STAGING=parity,staging
        importlib.reload(urls);clear_url_caches()
        for route in ('/cards/','/card-library/',path,'/api/card-groups/',
                      '/api/my-card-groups/','/api/card-group-filters/',
                      '/collection-assets/card-screens.js','/collection-assets/collection.js',
                      '/collection-assets/collection.css'):
            response=client.get(route)
            assert response.status_code==200,(parity,staging,route,response.status_code)
        page=client.get('/cards/').content.decode()
        assert '/collection-assets/card-screens.js' in page
        assert '/collection-assets/collection.js' in page
        assert b'species-screens.js' in client.get('/pokedex/2/').content
        projection=client.get('/api/pokedex-species/').json()
        assert len(projection['species'])==251
        if staging: assert all(row['species_artwork'] is None for row in projection['species'])
        profiles.append(dict(parity=parity,staging=staging,passed=True))
finally:
    settings.PARITY_ENABLED,settings.STAGING=old
    importlib.reload(urls);clear_url_caches()
original_flags=(settings.B2_ENABLED,settings.PARITY_ENABLED,settings.B3_ENABLED,settings.B4_ENABLED)
try:
    settings.B2_ENABLED=settings.PARITY_ENABLED=settings.B3_ENABLED=settings.B4_ENABLED=False
    importlib.reload(urls);clear_url_caches()
    original=client.get('/')
    assert original.status_code==200 and b'/collection-assets/navigation.js' not in original.content
    assert client.get('/pokedex/2/').status_code==200
    assert client.get('/cards/').status_code==404
    profiles.append(dict(profile='original-account-only',passed=True))
finally:
    settings.B2_ENABLED,settings.PARITY_ENABLED,settings.B3_ENABLED,settings.B4_ENABLED=original_flags
    importlib.reload(urls);clear_url_caches()
assert persisted_snapshot(root)==before,'Installed read-only probes changed persisted state'
print(json.dumps(dict(package_origin=str(package),installed_modules_and_assets=len(expected),
                     canonical_group=group['id'],route_profiles=profiles,
                     read_preservation_passed=True,provider_calls=0)))
"""
)
SERVER = (
    ORIGIN_CHECK
    + """
origin=dict(package_origin=str(package),python_prefix=sys.prefix,
            installed_modules_and_assets=len(expected),verified=True)
output=Path(sys.argv[4]);output.mkdir(parents=True,exist_ok=True)
(output/'installed-server-origin.json').write_text(json.dumps(origin,indent=2)+'\\n')
from serve_e4a import run
run(work/'engineering-root',output,int(sys.argv[5]))
"""
)


def b2_exercise(url, root, output, report):
    """Execute the installed group module with parity deliberately unavailable."""
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD
    from verify_cx05 import persisted_snapshot

    errors, external, parity_requests = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def restrict(route):
            if route.request.url.startswith(url + "/"):
                if "/api/parity/" in route.request.url:
                    parity_requests.append(route.request.url)
                route.continue_()
            else:
                assert route.request.resource_type == "image", route.request.url
                external.append(dict(url=route.request.url, sent_to_remote=False))
                route.abort("blockedbyclient")

        context.route("**/*", restrict)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def get(path):
            response = context.request.get(url + path)
            assert response.status == 200, (path, response.status)
            return response.json()

        try:
            page.goto(url + "/login/?next=/cards/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#content h1")).to_have_text("My Cards")
            assert page.locator("body").get_attribute("data-parity") == "false"
            assert page.evaluate("typeof window.renderCardScreens") == "function"
            assert page.locator('script[src="/collection-assets/parity.js"]').count() == 0
            before = persisted_snapshot(root)
            owned = get("/api/my-card-groups/")
            catalog = get("/api/card-groups/")
            assert owned["groups"] and all(group["present"] for group in owned["groups"])
            assert catalog["total"] > owned["total"]
            expect(page.locator(".owned-card-tile")).to_have_count(owned["total"])
            page.locator(".owned-card-tile").first.click()
            expect(page.locator("#content h1")).to_have_text(owned["groups"][0]["name"])
            expect(page.locator("#edit-group-card")).to_have_text("Edit collection")
            assert get("/api/card-groups/" + owned["groups"][0]["id"] + "/")["selected_child"] is None
            page.locator("#edit-group-card").click()
            expect(page.locator("dialog[open]")).to_have_count(1)
            page.keyboard.press("Escape")
            page.locator("#group-prices > summary").click()
            expect(page.locator("#group-prices-body")).to_contain_text(
                "Retained prices and source details are unavailable in this installation."
            )
            page.screenshot(path=str(output / "engineering-b2-optional-prices.png"), full_page=True)
            page.goto(url + "/card-library/")
            expect(page.locator("#content h1")).to_have_text("Card Library")
            expect(page.locator(".owned-card-tile")).to_have_count(catalog["total"])
            unowned = next(group for group in catalog["groups"] if not group["present"])
            page.goto(url + unowned["url"])
            expect(page.locator("#edit-group-card")).to_have_text("Add to collection")
            page.locator("#edit-group-card").click()
            expect(page.locator("dialog[open]")).to_have_count(1)
            page.keyboard.press("Escape")
            guest = browser.new_context()
            assert guest.request.get(url + "/api/my-card-groups/", max_redirects=0).status == 302
            assert "account_id" not in guest.request.get(url + "/api/public/card-groups/").text()
            guest.close()
            assert persisted_snapshot(root) == before, "B2 installed browsing/cancel altered persisted state"
            assert not parity_requests, parity_requests
            assert not errors, errors
            (output / "read-preservation.json").write_text(
                json.dumps(dict(before=before, after=persisted_snapshot(root), equal=True), indent=2) + "\n"
            )
            report["installed_b2_browser"] = dict(
                passed=True,
                parity_enabled=False,
                browser_version=browser.version,
                owned_total=owned["total"],
                catalog_total=catalog["total"],
                optional_price_unavailability_observed=True,
                parity_requests=0,
                external_requests_sent=0,
                controlled_external_images=external,
                read_preservation_passed=True,
                page_errors=errors,
            )
        finally:
            context.tracing.stop(path=str(output / "trace.zip"))
            browser.close()

    from verify_cx07 import exercise as species_exercise

    species_exercise(
        url,
        root,
        output,
        json.loads((root.parent / "fixture.json").read_text()),
        report,
        preserve_cards=False,
    )


def run_b2_server(python, inputs, work, output, expected_origin, report):
    """Restart only the disposable installed server with its parity marker saved."""
    marker = work / "engineering-root/B2_PARITY_ISOLATED"
    assert marker.is_file()
    marker.rename(work / "retained-B2_PARITY_ISOLATED")
    output.mkdir()
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    with (output / "server.log").open("w") as log:
        server = subprocess.Popen(
            [python, "-I", "-c", SERVER, *inputs, str(output), str(port)],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=work,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Installed B2 server exited before becoming ready")
                try:
                    with urlopen(url + "/login/", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Installed B2 server did not become ready")
            origin = json.loads((output / "installed-server-origin.json").read_text())
            assert origin["verified"] and origin["package_origin"] == expected_origin
            b2_exercise(url, work / "engineering-root", output, report)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
    calls = json.loads((output / "provider-calls.json").read_text())
    assert calls["calls"] == 0, calls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        evidence_class="fresh offline locked installed artifact; real installed UI in Chromium",
        customer_installation_accessed=False,
        CX08_complete=False,
        checks=[],
    )

    def run(command, cwd=PROJECT):
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
        report.setdefault("commands", []).append(
            dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        )
        assert result.returncode == 0, (command, result.stdout, result.stderr)
        return result

    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx07-installed-") as temporary:
            work = Path(temporary)
            artifacts = args.output / "artifacts"
            run([sys.executable, "-m", "hatchling", "build", "-t", "wheel", "-d", str(artifacts)])
            wheels = list(artifacts.glob("*.whl"))
            assert len(wheels) == 1, wheels
            wheel = wheels[0]
            expected = {}
            with zipfile.ZipFile(wheel) as archive:
                for name in REQUIRED:
                    data = archive.read(name)
                    assert data == (PROJECT / "src" / name).read_bytes(), name
                    expected[name] = hashlib.sha256(data).hexdigest()
            source_hashes = {"src/" + name: digest for name, digest in expected.items()}
            for name in ("scripts/verify_cx07.py", "scripts/verify_cx07_package.py", "uv.lock"):
                source_hashes[name] = hashlib.sha256((PROJECT / name).read_bytes()).hexdigest()
            report.update(
                wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                installed_input_hashes=expected,
                source_hashes=source_hashes,
                uv_lock_sha256=source_hashes["uv.lock"],
            )
            environment = work / "venv"
            runtime = work / "runtime-requirements.txt"
            run(["uv", "venv", "--offline", "--python", sys.executable, str(environment)])
            run(
                [
                    "uv",
                    "export",
                    "--offline",
                    "--locked",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                    "--output-file",
                    str(runtime),
                ]
            )
            python = str(environment / "bin/python")
            run(["uv", "pip", "sync", "--offline", "--python", python, "--require-hashes", str(runtime)])
            run(["uv", "pip", "install", "--offline", "--python", python, "--no-deps", str(wheel)])
            inputs = [json.dumps(expected), str(work), str(PROJECT / "scripts")]
            result = run([python, "-I", "-c", PROBE, *inputs], cwd=work)
            report["installed_probe"] = json.loads(result.stdout)
            port = free_port()
            url = f"http://127.0.0.1:{port}"
            with (args.output / "server.log").open("w") as log:
                server = subprocess.Popen(
                    [python, "-I", "-c", SERVER, *inputs, str(args.output), str(port)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=work,
                )
                try:
                    for _ in range(100):
                        if server.poll() is not None:
                            raise RuntimeError("Installed engineering server exited before becoming ready")
                        try:
                            with urlopen(url + "/login/", timeout=1) as response:
                                if response.status == 200:
                                    break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise RuntimeError("Installed engineering server did not become ready")
                    origin = json.loads((args.output / "installed-server-origin.json").read_text())
                    assert (
                        origin["verified"]
                        and origin["package_origin"] == report["installed_probe"]["package_origin"]
                    )
                    report["installed_server"] = origin
                    from verify_cx07 import exercise

                    exercise(
                        url,
                        work / "engineering-root",
                        args.output,
                        json.loads((work / "fixture.json").read_text()),
                        report,
                    )
                    report["installed_browser_execution_passed"] = True
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
            calls = json.loads((args.output / "provider-calls.json").read_text())
            assert calls["calls"] == 0, calls
            report["provider_calls"] = 0
            run_b2_server(
                python,
                inputs,
                work,
                args.output / "installed-b2",
                report["installed_probe"]["package_origin"],
                report,
            )
            assert source_hashes == {
                name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in source_hashes
            }, "Source changed during installed package verification"
            report["source_stable_during_verification"] = True
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["failure"] = traceback.format_exc()
        raise
    finally:
        (args.output / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
