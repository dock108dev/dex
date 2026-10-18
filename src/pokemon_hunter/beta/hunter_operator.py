"""Hash-pinned, read-only preflight and explicitly selected Hunter transition.

No command creates an authorization. Preflight imports no Django services, starts
no worker and opens state only read-only. Authority is a private operator document,
never HTTP input. Like the existing local operator, this is not an OS-user sandbox.
"""

import argparse
import fcntl
import hashlib
import importlib.metadata
import io
import json
import os
import re
import sqlite3
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

PLAN_ID = "hunt-04-qualification-v1"
COMPLETION_PLAN_ID = "hunt-07-completion-v1"
LIMITS = dict(oauth=1, browse=12, detail=2, resolution=0, total=15, auction=8, buy_it_now=4, lots=8)
PREDECESSOR_CONSUMED = dict(
    oauth=1, browse=2, detail=0, resolution=0, total=3, auction=1, buy_it_now=1, lots=0
)
PREDECESSOR_EXECUTION_SHA256 = "83eb166fdcac163017acc17e0998015b2bf9b36268de7f0b9cf75f61eab069d6"
PREDECESSOR_WHEEL_SHA256 = "497f147b1d1e9f98fc6e1d33acf0007da9b1d090253dcba3948152b724a377e9"
PREDECESSOR_LEDGER_SHA256 = "453f940e7afe239378aa31e426e9ea9b5d0d4d1ec7349700076a0b21189559f7"
PREDECESSOR_CLOSURE_SHA256 = "0405bcfc86ad0c9855a009587c75e39d5364aaabe4c8360e56f9055a6ed5e0b8"
HOST, PORT = "127.0.0.1", 8011
PROFILE = "hunter-execution-v1"
ACTUAL_ROOT = Path("/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local")
REQUIRED = {
    table: set(columns)
    for table, columns in json.loads(Path(__file__).with_name("hunter_execution_schema.json").read_text())[
        "tables"
    ].items()
}


class Refusal(ValueError):
    """Fixed content-free failure suitable for the operator terminal."""


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _document(path, *, private=False):
    target = Path(path)
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 2 * 1024 * 1024:
        raise Refusal("Operator document is unavailable")
    if private and (target.stat().st_uid != os.getuid() or target.stat().st_mode & 0o077):
        raise Refusal("Authorization must be an owner-only regular file")
    try:

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise Refusal("Duplicate operator document field")
                result[key] = value
            return result

        result = json.loads(target.read_bytes(), object_pairs_hook=unique)
    except (ValueError, UnicodeError):
        raise Refusal("Invalid operator document") from None
    if not isinstance(result, dict):
        raise Refusal("Invalid operator document")
    return result


def _path(value, *, directory=False):
    if not isinstance(value, str):
        raise Refusal("Invalid bound path")
    target = Path(value)
    if not target.is_absolute() or target != target.resolve(strict=True):
        raise Refusal("Bound path must be canonical without symlinks")
    if directory and not target.is_dir():
        raise Refusal("Bound directory is unavailable")
    return target


def schema_identity(root):
    """No application imports, cleanup, initialization or database creation."""
    database = root / "inventory.db"
    if database.is_symlink() or not database.is_file():
        raise Refusal("Existing database is unavailable")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        schema = db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
        ).fetchall()
        for table, required in REQUIRED.items():
            columns = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
            if not required <= columns:
                raise Refusal("Incompatible minimum schema; migration is not permitted")
        rows = db.execute(
            "SELECT u.id,u.auth_subject,u.role,u.state FROM users u JOIN auth_user a "
            "ON CAST(a.id AS TEXT)=u.auth_subject WHERE u.state='active' AND a.is_active=1"
        ).fetchall()
    return hashlib.sha256(canonical(schema)).hexdigest(), rows


def _files(entries):
    if not isinstance(entries, dict) or not entries:
        raise Refusal("Missing bound file identity")
    for name, expected in entries.items():
        # File symlinks (the existing .env contract) bind both link and target.
        target = Path(name)
        if not target.is_absolute() or not target.is_file() or digest(target) != expected:
            raise Refusal("Bound file identity changed")


def installed_identity(wheel, members, dependencies):
    if not isinstance(members, dict) or not members or not isinstance(dependencies, dict) or not dependencies:
        raise Refusal("Missing package or dependency identity")
    package_parent = Path(__file__).resolve().parents[2]
    installed_members = {
        "pokemon_hunter/" + str(path.relative_to(package_parent / "pokemon_hunter"))
        for path in (package_parent / "pokemon_hunter").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if installed_members != set(members):
        raise Refusal("Installed package member set changed")
    with zipfile.ZipFile(wheel) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.startswith("pokemon_hunter/") and not name.endswith("/")
        ]
        if len(names) != len(set(names)) or set(names) != set(members):
            raise Refusal("Wheel member set changed")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise Refusal("Unsafe wheel member")
            expected = members[name]
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise Refusal("Wheel member identity changed")
            if digest(package_parent / name) != expected:
                raise Refusal("Installed package differs from frozen wheel")
    for name, version in dependencies.items():
        if importlib.metadata.version(name) != version:
            raise Refusal("Dependency identity changed")
    # Reject additional dependency distributions too; package version alone is insufficient.
    installed = {
        re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower(): dist.version
        for dist in importlib.metadata.distributions()
        if re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower() != "pokemon-hunter"
    }
    if installed != dependencies:
        raise Refusal("Dependency member set changed")


def dependency_tree_identity():
    """Hash dependency bytes, including metadata and native extensions."""
    members = {}
    for dist in importlib.metadata.distributions():
        name = re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower()
        if name == "pokemon-hunter":
            continue
        if not dist.files:
            raise Refusal("Dependency file manifest is unavailable")
        for entry in dist.files:
            if str(entry).endswith(".pyc"):
                continue
            path = Path(dist.locate_file(entry))
            if not path.is_file():
                raise Refusal("Dependency member is unavailable")
            members[name + "/" + str(entry)] = digest(path)
    return hashlib.sha256(canonical(members)).hexdigest()


def runtime_tree_identity(root):
    """Include executables, virtualenv bootstrap, symlinks and dependency bytes."""
    root = _path(str(root), directory=True)
    members = {}
    for path in root.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            members[str(path.relative_to(root))] = {
                "link": os.readlink(path),
                "sha256": digest(path) if path.is_file() else None,
            }
        elif path.is_file():
            members[str(path.relative_to(root))] = {"sha256": digest(path)}
    return hashlib.sha256(canonical(members)).hexdigest()


def completion_plan_document(predecessor):
    """The single reviewed additional plan, never a caller-selected budget."""
    return dict(
        schema="dex-hunter-completion-plan-v1",
        id=COMPLETION_PLAN_ID,
        limits=dict(LIMITS),
        scope="both",
        ordering="unchanged-both-traversal",
        predecessor=predecessor,
        additional_operations=15,
        cumulative_hunt07_maximum=18,
        bounds=dict(
            browse_pages_per_action=2,
            summaries_per_page=200,
            page_bytes=2 * 1024 * 1024,
            fetched_summaries=2400,
            retained_summaries=800,
            retained_bytes=8 * 1024 * 1024,
            comparison_chunk=400,
            response_rows=200,
            response_bytes=2 * 1024 * 1024,
            request_seconds=30,
            action_seconds=75,
            original_lease_seconds=1800,
            exact_details=2,
        ),
    )


def validate_completion_predecessor(plan, root, kind, *, handback=False):
    """Bind completed history without restoring it or creating new capacity.

    Mutable accounting is rechecked before acquisition. It cannot prevent
    handback-only recovery, which still verifies the immutable selected linkage.
    """
    predecessor = plan.get("predecessor")
    if not isinstance(predecessor, dict):
        raise Refusal("Completion requires the closed predecessor identity")
    key = hashlib.sha256(str(root).encode()).hexdigest()
    ledger = root.parent / ".dex-shopping-discovery" / key / (PLAN_ID + ".jsonl")
    expected = dict(
        id=PLAN_ID,
        ledger=str(ledger),
        ledger_sha256=predecessor.get("ledger_sha256"),
        consumed=PREDECESSOR_CONSUMED,
        execution_sha256=PREDECESSOR_EXECUTION_SHA256,
        wheel_sha256=PREDECESSOR_WHEEL_SHA256,
        closed=True,
        closure_document=predecessor.get("closure_document"),
        closure_sha256=predecessor.get("closure_sha256"),
    )
    if canonical(predecessor) != canonical(expected) or any(
        not isinstance(predecessor.get(name), str) or not re.fullmatch(r"[0-9a-f]{64}", predecessor[name])
        for name in ("ledger_sha256", "closure_sha256")
    ):
        raise Refusal("Closed predecessor linkage changed")
    if kind == "proposed-production" and (
        predecessor["ledger_sha256"] != PREDECESSOR_LEDGER_SHA256
        or predecessor["closure_sha256"] != PREDECESSOR_CLOSURE_SHA256
    ):
        raise Refusal("Recorded production predecessor changed")
    closure = _path(predecessor["closure_document"])
    if digest(closure) != predecessor["closure_sha256"]:
        raise Refusal("Closed predecessor record changed")
    receipt = _document(closure)
    if (
        any(
            receipt.get(name) is not True
            for name in (
                "temporary_execution_completed",
                "latest_state_shop04_handback",
                "runtime_selection_closed",
                "provider_selection_closed",
            )
        )
        or type(receipt.get("consumed_attempts_preserved")) is not int
        or receipt["consumed_attempts_preserved"] != 3
        or type(receipt.get("unused_numeric_slots_not_reused")) is not int
        or receipt["unused_numeric_slots_not_reused"] != 12
        or receipt.get("allowance_reset") is not False
        or receipt.get("new_hunt_after_interruption") is not False
    ):
        raise Refusal("Predecessor selections are not recorded as closed")
    if handback:
        return
    if ledger.is_symlink() or any(parent.is_symlink() for parent in ledger.parents):
        raise Refusal("Predecessor ledger path contains a symlink")
    from .hunter_budget import MAX_TRAVERSAL_LEDGER_BYTES, TraversalAllowance, _traversal_counts

    try:
        with os.fdopen(os.open(ledger, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            data = stream.read(MAX_TRAVERSAL_LEDGER_BYTES + 1)
            if (
                len(data) > MAX_TRAVERSAL_LEDGER_BYTES
                or hashlib.sha256(data).hexdigest() != predecessor["ledger_sha256"]
            ):
                raise Refusal("Permanently consumed predecessor ledger changed")
            counts, _ = _traversal_counts(io.StringIO(data.decode()), TraversalAllowance(PLAN_ID, **LIMITS))
    except (OSError, UnicodeError, ValueError):
        raise Refusal("Permanently consumed predecessor accounting is unavailable") from None
    if canonical(counts) != canonical(PREDECESSOR_CONSUMED):
        raise Refusal("Predecessor consumed accounting changed")


def preflight(identity_path, expected_identity, *, handback=False):
    """Validate the entire frozen boundary before importing startup/services.

    Returns the private mapped account to the caller, never to diagnostics.
    Absence of a ledger is observed without making its parent directory.
    """
    if digest(identity_path) != expected_identity:
        raise Refusal("Execution identity changed")
    identity = _document(identity_path)
    if (
        set(identity)
        != {
            "schema",
            "kind",
            "profile",
            "root",
            "host",
            "port",
            "account_sha256",
            "schema_sha256",
            "python",
            "wheel",
            "wheel_sha256",
            "package_hashes",
            "dependencies",
            "dependency_tree_sha256",
            "runtime_trees",
            "bound_files",
            "launcher",
            "launcher_sha256",
            "profile_sha256",
            "plan",
            "handback",
            "configuration_root",
            "allowed_actions",
            "allowed_workers",
            "expected_writes",
        }
        or identity["schema"] != "dex-hunter-execution-v1"
    ):
        raise Refusal("Unsupported execution identity")
    if (
        identity["profile"] != PROFILE
        or identity["host"] != HOST
        or type(identity["port"]) is not int
        or identity["port"] != PORT
    ):
        raise Refusal("Execution profile or origin changed")
    root = _path(identity["root"], directory=True)
    if identity["kind"] == "proposed-production":
        if root != ACTUAL_ROOT:
            raise Refusal("Production root changed")
    elif identity["kind"] == "engineering":
        if root == ACTUAL_ROOT or not (root / "SYNTHETIC_ONLY").is_file():
            raise Refusal("Engineering identity requires a disposable fixture root")
    else:
        raise Refusal("Unsupported execution kind")
    if root.stat().st_mode & 0o077 or root.stat().st_uid != os.getuid():
        raise Refusal("Root must remain owner-only")
    if identity["python"] != str(Path(sys.executable).absolute()):
        raise Refusal("Candidate interpreter changed")
    if os.environ.get("DEX_PROFILE", "local") != "local":
        raise Refusal("Only the local profile is permitted")
    if any(
        os.environ.get(key)
        for key in (
            "EBAY_CLIENT_ID",
            "EBAY_CLIENT_SECRET",
            "EBAY_DELIVERY_POSTAL_CODE",
            "DJANGO_SETTINGS_MODULE",
            "DATABASE_URL",
        )
    ):
        raise Refusal("Unbound environment override is not permitted")
    wheel = _path(identity["wheel"])
    if digest(wheel) != identity["wheel_sha256"]:
        raise Refusal("Wheel identity changed")
    _files(identity["bound_files"])
    if digest(identity["launcher"]) != identity["launcher_sha256"]:
        raise Refusal("Launcher identity changed")
    if digest(Path(__file__).with_name("hunter_profile.py")) != identity["profile_sha256"]:
        raise Refusal("Execution profile bytes changed")
    plan = identity["plan"]
    if not isinstance(plan, dict) or plan.get("id") not in {PLAN_ID, COMPLETION_PLAN_ID}:
        raise Refusal("Unsupported reviewed finite plan")
    plan_id = plan["id"]
    key = hashlib.sha256(str(root).encode()).hexdigest()
    ledger = root.parent / ".dex-shopping-discovery" / key / (plan_id + ".jsonl")
    expected_plan = dict(
        id=plan_id,
        limits=LIMITS,
        ledger=str(ledger),
        document=plan.get("document"),
        sha256=plan.get("sha256"),
    )
    if plan_id == COMPLETION_PLAN_ID:
        expected_plan["predecessor"] = plan.get("predecessor")
    if (
        not isinstance(plan.get("limits"), dict)
        or any(type(plan["limits"].get(key)) is not int for key in LIMITS)
        or plan != expected_plan
    ):
        raise Refusal("Finite plan or ledger identity changed")
    if digest(plan["document"]) != plan["sha256"]:
        raise Refusal("Future plan document changed")
    if plan_id == COMPLETION_PLAN_ID and canonical(_document(plan["document"])) != canonical(
        completion_plan_document(plan["predecessor"])
    ):
        raise Refusal("Reviewed completion plan document changed")
    if ledger.is_symlink() or any(parent.is_symlink() for parent in ledger.parents):
        raise Refusal("Ledger path contains a symlink")
    installed_identity(wheel, identity["package_hashes"], identity["dependencies"])
    if dependency_tree_identity() != identity["dependency_tree_sha256"]:
        raise Refusal("Dependency bytes changed")
    schema, accounts = schema_identity(root)
    if schema != identity["schema_sha256"]:
        raise Refusal("Schema changed; migration is not permitted")
    selected = [
        row for row in accounts if hashlib.sha256(canonical(row)).hexdigest() == identity["account_sha256"]
    ]
    if len(selected) != 1 and not handback:
        raise Refusal("Expected active account changed")
    saved_handback = identity["handback"]
    if set(saved_handback) != {"python", "helper", "helper_sha256", "python_sha256"}:
        raise Refusal("Unsupported handback pointers")
    _files(
        {
            saved_handback["python"]: saved_handback["python_sha256"],
            saved_handback["helper"]: saved_handback["helper_sha256"],
        }
    )
    runtime_trees = identity["runtime_trees"]
    required_runtimes = {
        str(Path(identity["python"]).parent.parent),
        str(Path(saved_handback["python"]).parent.parent),
    }
    if not isinstance(runtime_trees, dict) or set(runtime_trees) != required_runtimes:
        raise Refusal("Candidate and SHOP-04 runtime identities are required")
    for runtime, expected in runtime_trees.items():
        if runtime_tree_identity(runtime) != expected:
            raise Refusal("Candidate or saved SHOP-04 runtime bytes changed")
    configuration_root = _path(identity["configuration_root"], directory=True)
    for file in (
        configuration_root / ".env",
        configuration_root / "config/settings.yaml",
        root / "secret.key",
        root / "B1_ISOLATED",
        root / "B2_ISOLATED",
    ):
        if file.is_file() and str(file) not in identity["bound_files"]:
            raise Refusal("Required private configuration or root marker is unbound")
    # Import only after frozen package, profile and minimum schema were checked.
    from . import hunter_profile
    from .hunter_budget import TraversalAllowance, remaining_traversal

    if plan_id == COMPLETION_PLAN_ID:
        validate_completion_predecessor(plan, root, identity["kind"], handback=handback)
    if not handback:
        remaining_traversal(root, TraversalAllowance(plan_id, **LIMITS))

    if (
        identity["allowed_actions"] != list(hunter_profile.ALLOWED_ACTIONS)
        or identity["allowed_workers"] != list(hunter_profile.ALLOWED_WORKERS)
        or identity["expected_writes"] != list(hunter_profile.EXPECTED_WRITES)
    ):
        raise Refusal("Selected actions, workers or write set changed")
    return identity, selected[0][0] if selected else None


def authorization(
    path, execution_sha256, plan_sha256, *, plan_id=PLAN_ID, require_provider=True, handback=False
):
    if plan_id not in {PLAN_ID, COMPLETION_PLAN_ID}:
        raise Refusal("Unsupported reviewed provider plan")
    value = _document(path, private=True)
    if (
        set(value) != {"schema", "execution_sha256", "runtime_transition", "provider_plan", "expires_at"}
        or value["schema"] != "dex-hunter-authorization-v1"
        or value["execution_sha256"] != execution_sha256
    ):
        raise Refusal("Authorization does not select this execution identity")
    try:
        expires = datetime.fromisoformat(value["expires_at"])
        if expires.utcoffset() is None or (expires <= datetime.now(UTC) and not handback):
            raise ValueError
    except (TypeError, ValueError):
        raise Refusal("Authorization is expired or invalid") from None
    if value["runtime_transition"] is not True:
        raise Refusal("Temporary runtime transition is not selected")
    selection = value["provider_plan"]
    provider = (
        isinstance(selection, dict)
        and selection.get("selected") is True
        and selection == {"id": plan_id, "sha256": plan_sha256, "selected": True}
    )
    if require_provider and not provider:
        raise Refusal("Exact finite provider plan is not separately selected")
    return provider


def acquisition_authorization(identity, authorization_path, execution_sha256):
    """Recheck completion linkage and selection before sends and publication."""
    plan = identity["plan"]
    if plan.get("id") == COMPLETION_PLAN_ID:
        validate_completion_predecessor(plan, Path(identity["root"]), identity["kind"])
    return authorization(
        authorization_path, execution_sha256, plan["sha256"], plan_id=plan.get("id", PLAN_ID)
    )


def serve(identity_path, expected_identity, authorization_path):
    identity, account = preflight(identity_path, expected_identity)
    if identity["kind"] != "proposed-production":
        raise Refusal("Engineering execution is available only through fake-transport tests")
    acquisition_authorization(identity, authorization_path, expected_identity)
    # Direct child startup cannot bypass the transition's normal Stop/backup.
    key = hashlib.sha256(identity["root"].encode()).hexdigest()
    marker = Path(identity["root"]).parent / ".dex-hunter-transition" / key / "pending.json"
    if _document(marker, private=True) != {
        "identity_digest": expected_identity,
        "phase": "candidate-starting",
    }:
        raise Refusal("Candidate startup requires the selected transition boundary")
    import subprocess

    listener = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP:8011", "-sTCP:LISTEN", "-Fp"], capture_output=True, check=False
    )
    if listener.returncode != 1 or listener.stdout.strip():
        raise Refusal("Ordinary origin must be free before restricted startup")
    from . import cli, hunter_budget, hunter_profile

    hunter_profile.configure(
        account,
        Path(identity["root"]),
        configuration_root=Path(identity["configuration_root"]),
        authorization_check=lambda: acquisition_authorization(
            identity, authorization_path, expected_identity
        ),
        plan_id=identity["plan"]["id"],
    )
    cli.setup(Path(identity["root"]))
    hunter_budget.TRAVERSAL_ALLOWANCE = hunter_budget.TraversalAllowance(identity["plan"]["id"], **LIMITS)
    try:
        hunter_profile.serve()
    finally:
        hunter_budget.TRAVERSAL_ALLOWANCE = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "execute", "handback", "serve"))
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--expected-identity", required=True)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    try:
        identity, _ = preflight(args.identity, args.expected_identity, handback=args.action == "handback")
        if args.action == "preflight":
            print(json.dumps(dict(status="preflight_pass", activated=False, provider_operations=0)))
            return
        if args.authorization is None:
            raise Refusal("Separate runtime-transition and provider authorization is required")
        if args.action == "serve":
            serve(args.identity, args.expected_identity, args.authorization)
            return
        authorization(
            args.authorization,
            args.expected_identity,
            identity["plan"]["sha256"],
            require_provider=args.action == "execute",
            handback=args.action == "handback",
            plan_id=identity["plan"]["id"],
        )
        if identity["kind"] != "proposed-production":
            raise Refusal("Engineering transitions use only disposable test adapters")
        from .hunter_transition import (
            HandbackRequired,
            LocalProcessAdapter,
            RuntimeTransitionAuthorization,
            TransitionPlan,
            TransitionRefused,
            retry_handback,
            run_transition,
        )

        handback = identity["handback"]
        candidate_argv = (
            identity["python"],
            "-I",
            identity["launcher"],
            "serve",
            "--identity",
            str(args.identity.resolve()),
            "--expected-identity",
            args.expected_identity,
            "--authorization",
            str(args.authorization.resolve()),
        )
        plan = TransitionPlan(
            root=Path(identity["root"]),
            candidate_argv=candidate_argv,
            shop_python=Path(handback["python"]),
            startup_helper=Path(handback["helper"]),
            helper_sha256=handback["helper_sha256"],
            shop_python_sha256=handback["python_sha256"],
            identity_digest=args.expected_identity,
            schema_digest=identity["schema_sha256"],
        )
        adapter = LocalProcessAdapter(
            plan,
            verify_identity=lambda: preflight(args.identity, args.expected_identity),
            verify_handback_identity=lambda: preflight(args.identity, args.expected_identity, handback=True),
        )
        selected = RuntimeTransitionAuthorization(args.expected_identity, selected=True)
        try:
            if args.action == "handback":
                result = retry_handback(plan, selected, adapter)
            else:

                def wait_for_completion(adapter):
                    input(
                        "Hunter is ready at the ordinary origin. Press Enter to Stop and return to SHOP-04.\n"
                    )

                result = run_transition(plan, selected, adapter, wait_for_completion)
        except HandbackRequired as exc:
            raise SystemExit(
                str(exc)
                + ". Latest state is preserved; use handback with the same identity. Compatibility failures require forward repair."
            ) from None
        except TransitionRefused as exc:
            raise SystemExit("Guarded transition refused: " + str(exc)) from None
        from dataclasses import asdict

        print(json.dumps(asdict(result), sort_keys=True))
    except Refusal as exc:
        raise SystemExit("Guarded Hunter operation refused: " + str(exc)) from None
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        sqlite3.Error,
        zipfile.BadZipFile,
        importlib.metadata.PackageNotFoundError,
        RuntimeError,
    ):
        # Never print paths, document contents, account IDs, credentials or provider errors.
        raise SystemExit(
            "Guarded Hunter operation refused; verify the frozen identity and separate authorizations."
        ) from None


if __name__ == "__main__":
    main()
