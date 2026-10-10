"""Pure wheel/sdist inspection and required runtime inputs for the distribution gate.

These checks read archives without extraction or application imports. Installed
startup, provider isolation and subprocess cleanup belong to the smoke harness.
"""

import hashlib
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

REQUIRED_FILES = (
    "pokemon_hunter/main.py",
    "pokemon_hunter/runtime_data.py",
    "pokemon_hunter/beta/synthetic.py",
    "pokemon_hunter/beta/asgi.py",
    "pokemon_hunter/beta/lot_calculator.py",
    "pokemon_hunter/beta/shopping.py",
    "pokemon_hunter/beta/shopping_inputs.py",
    "pokemon_hunter/beta/shopping_math.py",
    "pokemon_hunter/beta/shopping_views.py",
    "pokemon_hunter/beta/retained_guide_admission.json",
    "pokemon_hunter/beta/templates/beta/lot_calculator.html",
    "pokemon_hunter/beta/templates/beta/shopping.html",
    "pokemon_hunter/beta/static/lot_calculator.css",
    "pokemon_hunter/beta/static/lot_calculator.js",
    "pokemon_hunter/beta/static/shopping.css",
    "pokemon_hunter/beta/static/shopping.js",
    "pokemon_hunter/beta/templates/beta/public_pokedex.html",
    "pokemon_hunter/beta/templates/beta/login.html",
    "pokemon_hunter/beta/static/glass.css",
    "pokemon_hunter/beta/static/public.css",
    "pokemon_hunter/beta/static/parity.js",
    "pokemon_hunter/data/config/sealed/2026-10-04/package.json",
    "pokemon_hunter/data/config/catalog-imports/gym-heroes.json",
    "pokemon_hunter/data/config/catalog-imports/synthetic-orbits.json",
    "pokemon_hunter/data/config/catalog-imports/staging-ten/base_set.json",
    "pokemon_hunter/data/config/catalog-pipeline/inputs.json",
    "pokemon_hunter/data/config/catalog-pipeline/m4-20261006/coverage-profile.json",
)


PRIVATE_NAMES = {".env", "settings.yaml", "pokedex_251.json", "secret.key", "credentials.json"}


class SmokeFailure(RuntimeError):
    pass


def inspect_wheel(wheel):
    with zipfile.ZipFile(wheel) as archive:
        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
        names = {entry.filename for entry in entries}
        if len(names) != len(entries):
            raise SmokeFailure("Wheel contains duplicate file names")
        if any(name.startswith("/") or ".." in PurePosixPath(name).parts for name in names):
            raise SmokeFailure("Wheel contains unsafe paths")
        missing = set(REQUIRED_FILES) - names
        if missing:
            raise SmokeFailure("Wheel is missing required runtime files: " + ", ".join(sorted(missing)))
        if any(Path(name).name in PRIVATE_NAMES for name in names):
            raise SmokeFailure("Wheel contains a private state or configuration filename")
        if any(Path(name).suffix in {".db", ".sqlite3"} for name in names):
            raise SmokeFailure("Wheel contains a local database")
        hashes = {
            name: hashlib.sha256(archive.read(name)).hexdigest()
            for name in sorted(names)
            if name.startswith("pokemon_hunter/")
        }
        return {
            "wheel_bytes": wheel.stat().st_size,
            "wheel_uncompressed_bytes": sum(entry.file_size for entry in entries),
            "wheel_file_count": len(entries),
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        }, hashes


def inspect_sdist(sdist, wheel_hashes):
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        if any(member.issym() or member.islnk() for member in members):
            raise SmokeFailure("Source distribution contains symbolic or hard links")
        files = [member for member in members if member.isfile()]
        paths = [PurePosixPath(member.name) for member in files]
        if any(path.is_absolute() or ".." in path.parts or len(path.parts) < 2 for path in paths):
            raise SmokeFailure("Source distribution contains unsafe paths")
        if len({path.parts[0] for path in paths}) != 1:
            raise SmokeFailure("Source distribution lacks a single package root")
        relative = {str(PurePosixPath(*path.parts[1:])): member for path, member in zip(paths, files)}
        if len(relative) != len(files):
            raise SmokeFailure("Source distribution contains duplicate file names")
        if any(PurePosixPath(name).name in PRIVATE_NAMES for name in relative):
            raise SmokeFailure("Source distribution contains private state or configuration")
        if any(PurePosixPath(name).suffix in {".db", ".sqlite3"} for name in relative):
            raise SmokeFailure("Source distribution contains a local database")
        if not {"pyproject.toml", "uv.lock"}.issubset(relative):
            raise SmokeFailure("Source distribution is missing its locked build inputs")
        for name, expected in wheel_hashes.items():
            source_name = (
                name.removeprefix("pokemon_hunter/data/")
                if name.startswith("pokemon_hunter/data/")
                else "src/" + name
            )
            if source_name not in relative:
                raise SmokeFailure("Source distribution is missing wheel input: " + source_name)
            with archive.extractfile(relative[source_name]) as data:
                if hashlib.sha256(data.read()).hexdigest() != expected:
                    raise SmokeFailure("Source distribution differs from wheel input: " + source_name)
        return {
            "sdist_bytes": sdist.stat().st_size,
            "sdist_uncompressed_bytes": sum(member.size for member in files),
            "sdist_file_count": len(files),
            "sdist_sha256": hashlib.sha256(sdist.read_bytes()).hexdigest(),
        }
