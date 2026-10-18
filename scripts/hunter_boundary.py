"""Supported hash-pinned bootstrap. Does not import application code before checks."""

import hashlib
import json
import runpy
import sys
import sysconfig
import zipfile
from pathlib import Path


def verify_package(identity):
    """Check all executable/package bytes before importing even __init__.py."""
    wheel = Path(identity["wheel"])
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != identity["wheel_sha256"]:
        raise ValueError
    members = identity["package_hashes"]
    parent = Path(sysconfig.get_path("purelib"))
    package = parent / "pokemon_hunter"
    actual = {
        "pokemon_hunter/" + str(path.relative_to(package))
        for path in package.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if actual != set(members):
        raise ValueError
    with zipfile.ZipFile(wheel) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.startswith("pokemon_hunter/") and not name.endswith("/")
        ]
        if len(names) != len(set(names)) or set(names) != set(members):
            raise ValueError
        for name, expected in members.items():
            if ".." in Path(name).parts or Path(name).is_absolute():
                raise ValueError
            if (
                hashlib.sha256(archive.read(name)).hexdigest() != expected
                or hashlib.sha256((parent / name).read_bytes()).hexdigest() != expected
            ):
                raise ValueError


def main():
    try:
        args = sys.argv[1:]
        path = Path(args[args.index("--identity") + 1])
        expected = args[args.index("--expected-identity") + 1]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError
        identity = json.loads(path.read_text())
        if (
            Path(identity["launcher"]).resolve() != Path(__file__).resolve()
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != identity["launcher_sha256"]
        ):
            raise ValueError
        if str(Path(sys.executable).absolute()) != identity["python"]:
            raise ValueError
        if not sys.flags.isolated:
            raise ValueError
        verify_package(identity)
    except (OSError, ValueError, KeyError, IndexError, TypeError, zipfile.BadZipFile):
        raise SystemExit("Guarded Hunter bootstrap refused: frozen identity mismatch.") from None
    # Stay in this process: ps retains the exact bootstrap command so the
    # transition can identify and stop its child without PID guessing.
    runpy.run_module("pokemon_hunter.beta.hunter_operator", run_name="__main__")


if __name__ == "__main__":
    main()
