"""Build offline and smoke artwork roles and fallback routes routes from a fresh installed wheel.

Runtime dependencies are installed from the existing lock into a new isolated
environment. Both package origin and relevant module/asset bytes are checked.
The route smoke uses disposable engineering state and forbids network requests.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "pokemon_hunter/beta/card_groups.py",
    "pokemon_hunter/beta/card_group_views.py",
    "pokemon_hunter/beta/urls.py",
    "pokemon_hunter/beta/parity.py",
    "pokemon_hunter/beta/static/collection.js",
    "pokemon_hunter/beta/static/parity.js",
    "pokemon_hunter/beta/templates/beta/b2.html",
    "pokemon_hunter/beta/image_mappings.py",
    "pokemon_hunter/beta/image_bindings.py",
    "pokemon_hunter/beta/data/cx04_image_mappings.json",
    "pokemon_hunter/beta/owned_artwork.py",
    "pokemon_hunter/beta/scans.py",
    "pokemon_hunter/beta/scan_views.py",
    "pokemon_hunter/beta/security.py",
    "pokemon_hunter/beta/collection_views.py",
    "pokemon_hunter/beta/static/pokedex.js",
    "pokemon_hunter/beta/static/collection.css",
)
PROBE = """
import hashlib, json, os, socket, sys
from pathlib import Path
expected=json.loads(sys.argv[1]); work=Path(sys.argv[2]); scripts=sys.argv[3]
os.environ['DEX_PROFILE']='local'
def prohibit(*args, **kwargs):
    raise AssertionError('Installed route smoke forbids network/provider requests')
socket.socket.connect=prohibit
socket.socket.connect_ex=prohibit
import pokemon_hunter
package=Path(pokemon_hunter.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix).resolve()), package
assert package.parent.name != 'src', package
for name, digest in expected.items():
    assert hashlib.sha256((package.parent/name).read_bytes()).hexdigest()==digest, name
sys.path.insert(0,scripts)
from verify_cx04 import prepare, persisted_snapshot
root=work/'engineering-root'; fixture=work/'fixture.json'
prepare(root,work/'source',fixture)
from pokemon_hunter.beta import card_groups, card_group_views
fixture=json.loads(fixture.read_text())
from django.test import Client
from qualify_shopping import PASSWORD
client=Client(HTTP_HOST='127.0.0.1:8011',REMOTE_ADDR='127.0.0.1')
assert client.get('/login/').status_code==200
signed=client.post('/login/',dict(username='admin',password=PASSWORD,
                  csrfmiddlewaretoken=client.cookies['dex_b1_csrf'].value))
assert signed.status_code==302, signed.content
before=persisted_snapshot(root)
listing=client.get('/api/card-groups/')
assert listing.status_code==200, listing.content
group=next(row for row in listing.json()['groups'] if row['name']=='Ivysaur')
assert group['reference_image']['image_url'].endswith('/base/base4/44/low.webp')
from pokemon_hunter.beta import image_mappings
assert image_mappings.species_artwork(251)['image_url'].endswith('/251.png')
assert len(image_mappings._reviewed()['species'])==251
assert len(image_mappings._reviewed()['cards'])==21516
plain=client.get('/api/card-groups/'+group['id']+'/').json()
assert plain['selected_child'] is None and plain['selected_child_image'] is None
chosen=client.get('/api/card-groups/'+group['id']+'/?child='+fixture['selected_printing']).json()
assert chosen['selected_child_image']['availability']=='unavailable'
assert 'reference_image' not in client.get('/api/public/card-groups/').content.decode()
path='/card-groups/'+group['id']+'/' 
selected='?child='+fixture['selected_printing']
for route in ('/api/card-groups/'+group['id']+'/',
              '/api/card-groups/'+group['id']+'/'+selected,
              '/api/my-card-groups/', '/api/public/card-groups/',
              '/api/public/card-groups/'+group['id']+'/', path+selected,
              '/collection-assets/parity.js'):
    response=client.get(route)
    assert response.status_code==200, (route,response.status_code)
legacy=client.get('/cards/'+fixture['selected_alias']+'/')
assert legacy.status_code==302 and legacy.url==path+selected, (legacy.status_code,legacy.url)
assert client.get('/api/card-groups/'+group['id']+'/?child='+fixture['foreign_printing']).status_code==404
assert client.get('/cards/'+fixture['ambiguous_alias']+'/').status_code==409
assert persisted_snapshot(root)==before, 'Installed route reads changed persisted state'
print(json.dumps(dict(package_origin=str(package),installed_modules_and_assets=len(expected),
                     canonical_group=group['id'], route_smoke_passed=True,
                     read_preservation_passed=True, provider_calls=0)))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(evidence_class="fresh locked installed artifact; isolated engineering route smoke")

    def run(command, cwd=PROJECT):
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
        report.setdefault("commands", []).append(
            dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        )
        assert result.returncode == 0, (command, result.stdout, result.stderr)
        return result

    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx04-installed-") as temporary:
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
            report.update(
                wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                installed_input_hashes=expected,
                uv_lock_sha256=hashlib.sha256((PROJECT / "uv.lock").read_bytes()).hexdigest(),
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
            result = run(
                [python, "-I", "-c", PROBE, json.dumps(expected), str(work), str(PROJECT / "scripts")],
                cwd=work,
            )
            report["installed_probe"] = json.loads(result.stdout)
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["failure"] = traceback.format_exc()
        raise
    finally:
        (args.output / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
