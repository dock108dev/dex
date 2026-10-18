"""Guarded local runtime transition; handback always uses the latest private state.

This module has no allowance activation, credential or provider transport code.
The trusted operator supplies a read-only frozen-identity verifier. All production
mutations require a separately digest-bound runtime selection. Backups are for
protection only: no restore operation is implemented or called by handback.
"""

import contextlib
import fcntl
import hashlib
import json
import os
import shlex
import shutil
import signal
import socket
import sqlite3
import stat
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


class TransitionRefused(ValueError):
    """A fixed, content-free reason suitable for a local operator."""


class HandbackRequired(RuntimeError):
    """Latest state is intact; the recorded handback must be retried or repaired."""


@dataclass(frozen=True)
class TransitionPlan:
    root: Path
    candidate_argv: tuple[str, ...]
    shop_python: Path
    startup_helper: Path
    helper_sha256: str
    shop_python_sha256: str
    identity_digest: str
    schema_digest: str
    host: str = "127.0.0.1"
    port: int = 8011

    @property
    def shop_argv(self):
        return (
            str(self.shop_python),
            "-I",
            "-m",
            "pokemon_hunter.beta.cli",
            "--root",
            str(self.root),
            "serve",
        )


@dataclass(frozen=True)
class RuntimeTransitionAuthorization:
    identity_digest: str
    selected: bool = False


@dataclass(frozen=True)
class TransitionResult:
    completed: bool
    handed_back: bool
    phases: tuple[str, ...]


def file_digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def schema_digest(root):
    """Read SQLite schema without setup, startup callbacks or migrations."""
    path = Path(root) / "inventory.db"
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
        ).fetchall()
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _validate(plan, authorization):
    if (
        not isinstance(authorization, RuntimeTransitionAuthorization)
        or authorization.selected is not True
        or authorization.identity_digest != plan.identity_digest
    ):
        raise TransitionRefused("Exact runtime-transition selection required")
    if plan.host != "127.0.0.1" or plan.port != 8011:
        raise TransitionRefused("Ordinary loopback origin required")
    if not plan.root.is_absolute() or plan.root != plan.root.resolve(strict=True):
        raise TransitionRefused("Canonical existing root required")
    if not plan.candidate_argv or not Path(plan.candidate_argv[0]).is_absolute():
        raise TransitionRefused("Exact installed candidate command required")
    if tuple(plan.candidate_argv) == plan.shop_argv:
        raise TransitionRefused("Distinct isolated candidate required")


def run_transition(plan, authorization, adapter, session):
    """Run one selected session, then return to compatible SHOP-04 on latest state.

    ``session`` may wait for local completion, Stop or user interruption; it must
    never silently activate or dispatch provider work. A production child uses
    its own restricted profile's shutdown hooks to cancel/erase temporary work.
    """
    _validate(plan, authorization)
    if adapter.plan != plan:
        raise TransitionRefused("Adapter does not match the frozen transition plan")
    phases = []
    adapter.preflight(require_shop=True)
    with adapter.lock(), _term_as_interrupt():
        if adapter.pending():
            raise TransitionRefused("Pending handback requires handback-only recovery")
        # Recheck under the exclusive operator lock, immediately before stopping.
        adapter.preflight(require_shop=True)
        try:
            adapter.record("shop-stopping")
            adapter.stop_shop()
            phases.append("shop-stopped")
            adapter.record("backup")
            adapter.backup()
            phases.append("protected-backup")
            adapter.preflight(require_shop=False)
            adapter.record("candidate-starting")
            adapter.start_candidate()
            phases.append("candidate-started")
            adapter.record("candidate-running")
            session(adapter)
            phases.append("session-completed")
        except BaseException:
            _handback(adapter, phases)
            raise
        _handback(adapter, phases)
    return TransitionResult(True, True, tuple(phases))


def retry_handback(plan, authorization, adapter):
    """Resume only the return operation; never restart Hunter or repeat backup."""
    _validate(plan, authorization)
    if adapter.plan != plan:
        raise TransitionRefused("Adapter does not match the frozen transition plan")
    phases = []
    with adapter.lock(), _term_as_interrupt():
        if not adapter.pending():
            raise TransitionRefused("No matching pending transition")
        _handback(adapter, phases)
    return TransitionResult(False, True, tuple(phases))


@contextlib.contextmanager
def _term_as_interrupt():
    # Normal operator termination follows the same cleanup as Ctrl-C. SIGKILL
    # cannot be trapped; the durable marker makes its handback retry explicit.
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.getsignal(signal.SIGTERM)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _handback(adapter, phases):
    try:
        adapter.record("candidate-stopping")
        adapter.stop_candidate()
        phases.append("candidate-stopped")
        adapter.record("shop-compatibility")
        adapter.verify_handback()
        adapter.record("shop-starting")
        adapter.start_shop()
        phases.append("shop-latest-state-started")
        adapter.clear_pending()
    except BaseException as exc:
        reason = str(exc) if isinstance(exc, (TransitionRefused, HandbackRequired)) else "Return interrupted"
        raise HandbackRequired("Latest-state handback incomplete: " + reason) from None


# Provider summaries/details/reviews are memory-only. These additional common
# transient names fail closed rather than being copied into a protected backup.
BACKUP_EXCLUDED = frozenset(
    {
        "price-snapshots",
        "__pycache__",
        ".cache",
        "provider-cache",
        "hunter-results",
        "hunter-details",
        "discovery-cache",
        "tmp",
    }
)


class LocalProcessAdapter:
    """Supported Unix/macOS adapter using ordinary local CLI process conventions.

    Construction and preflight are read-only. ``verify_identity`` must revalidate
    installed wheel/dependencies, profile/bootstrap, account boundary, ledger,
    allowed actions/writes and the canonical plan, without Django setup. It must
    not compare mutable session/journal bytes to an old baseline.
    """

    def __init__(
        self, plan, verify_identity, *, verify_handback_identity=None, backup_parent=None, timeout=15
    ):
        self.plan = plan
        self.verify_identity = verify_identity
        self.verify_handback_identity = verify_handback_identity or verify_identity
        self.timeout = timeout
        root_hash = hashlib.sha256(str(plan.root).encode()).hexdigest()
        self.control = plan.root.parent / ".dex-hunter-transition" / root_hash
        self.marker = self.control / "pending.json"
        self.backup_parent = backup_parent or plan.root.parent / ".dex-transition-backups" / root_hash
        self.children = {}

    def _pointers(self):
        if file_digest(self.plan.startup_helper) != self.plan.helper_sha256:
            raise TransitionRefused("Saved startup helper changed")
        if file_digest(self.plan.shop_python) != self.plan.shop_python_sha256:
            raise TransitionRefused("Saved SHOP-04 interpreter changed")
        if schema_digest(self.plan.root) != self.plan.schema_digest:
            raise TransitionRefused("Latest schema incompatible with saved runtime")

    def preflight(self, *, require_shop):
        self.verify_identity()
        self._pointers()
        self._process_state(require_shop=require_shop)
        self._compatible_shop_runtime()

    def _compatible_shop_runtime(self):
        # Import/check the SAVED runtime against latest state with a read-only
        # SQLite URI; no serve, migration, lifecycle worker or request path runs.
        script = """
import os, sys
from pathlib import Path
os.environ["DEX_PROFILE"] = "local"
os.environ["DEX_B1_ROOT"] = sys.argv[1]
os.environ["DJANGO_SETTINGS_MODULE"] = "pokemon_hunter.beta.settings"
from pokemon_hunter.beta import settings as config
config.DATABASES["default"]["NAME"] = (Path(sys.argv[1]) / "inventory.db").as_uri() + "?mode=ro"
config.DATABASES["default"]["OPTIONS"] = {"uri": True, "timeout": 5}
import django
django.setup()
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
call_command("check", verbosity=0)
executor = MigrationExecutor(connection)
if executor.migration_plan(executor.loader.graph.leaf_nodes()):
    raise RuntimeError("Required saved-runtime schema is not already applied")
connection.close()
"""
        try:
            result = subprocess.run(
                [str(self.plan.shop_python), "-I", "-B", "-c", script, str(self.plan.root)],
                cwd=self.plan.root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise TransitionRefused("Saved runtime read-only compatibility check failed") from None
        if result.returncode != 0:
            raise TransitionRefused("Saved runtime read-only compatibility check failed")

    def _processes(self, argv):
        result = subprocess.run(
            ["/bin/ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            check=True,
        )
        found = []
        for line in result.stdout.splitlines():
            fields = line.strip().split(None, 1)
            if len(fields) != 2:
                continue
            try:
                if tuple(shlex.split(fields[1])) == tuple(argv):
                    found.append(int(fields[0]))
            except ValueError:
                continue
        if len(found) > 1:
            raise TransitionRefused("Duplicate ordinary-root processes")
        return found

    def _listener(self):
        lsof = shutil.which("lsof") or "/usr/sbin/lsof"
        result = subprocess.run(
            [lsof, "-nP", "-iTCP:8011", "-sTCP:LISTEN", "-FpFn"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 1 and not result.stdout.strip():
            return None
        if result.returncode != 0:
            raise TransitionRefused("Cannot inspect ordinary listener")
        pids = {int(line[1:]) for line in result.stdout.splitlines() if line.startswith("p")}
        names = {line[1:] for line in result.stdout.splitlines() if line.startswith("n")}
        if len(pids) != 1 or names != {"127.0.0.1:8011"}:
            raise TransitionRefused("Ordinary origin has an unexpected listener")
        return pids.pop()

    def _process_state(self, *, require_shop):
        shop = self._processes(self.plan.shop_argv)
        candidate = self._processes(self.plan.candidate_argv)
        listener = self._listener()
        if candidate or (require_shop and (not shop or listener != shop[0])):
            raise TransitionRefused("Expected ordinary SHOP-04 process required")
        if not require_shop and (shop or listener is not None):
            raise TransitionRefused("Ordinary origin must be free before candidate startup")

    def _private_directory(self, path, *, create):
        path = Path(path)
        base = self.plan.root.parent
        if not path.is_absolute() or not path.is_relative_to(base):
            raise TransitionRefused("Transition storage must stay beside the canonical root")
        current = base
        for component in path.relative_to(base).parts:
            current = current / component
            if current.is_symlink():
                raise TransitionRefused("Transition storage refuses symlink paths")
            if not current.exists():
                if not create:
                    return False
                current.mkdir(mode=0o700)
            info = current.stat(follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise TransitionRefused("Transition storage must be an owner-only directory")
        return True

    def _regular(self, path):
        if path.is_symlink():
            raise TransitionRefused("Transition storage refuses symlink files")
        if not path.exists():
            return False
        info = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise TransitionRefused("Transition control file must be owner-only and regular")
        return True

    @contextlib.contextmanager
    def lock(self):
        self._private_directory(self.control, create=True)
        path = self.control / "operator.lock"
        self._regular(path)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a+b") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise TransitionRefused("Another transition operator is active") from None
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def pending(self):
        if not self._private_directory(self.control, create=False) or not self._regular(self.marker):
            return False
        if self.marker.stat().st_size > 4096:
            raise TransitionRefused("Unreadable pending handback marker")
        try:
            descriptor = os.open(self.marker, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "r", encoding="utf-8") as source:
                data = json.load(source)
        except (OSError, ValueError):
            raise TransitionRefused("Unreadable pending handback marker") from None
        if not isinstance(data, dict) or set(data) != {"identity_digest", "phase"}:
            raise TransitionRefused("Unreadable pending handback marker")
        if data.get("identity_digest") != self.plan.identity_digest:
            raise TransitionRefused("Pending handback belongs to another identity")
        return True

    def record(self, phase):
        self._private_directory(self.control, create=False)
        self._regular(self.marker)
        temporary = self.control / ("pending-" + uuid.uuid4().hex + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump({"identity_digest": self.plan.identity_digest, "phase": phase}, output)
                output.flush()
                os.fsync(output.fileno())
            self._regular(self.marker)
            os.replace(temporary, self.marker)
        finally:
            temporary.unlink(missing_ok=True)
        directory = os.open(self.control, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def clear_pending(self):
        self._private_directory(self.control, create=False)
        self._regular(self.marker)
        self.marker.unlink()

    def _stop(self, argv):
        pids = self._processes(argv)
        if not pids:
            return
        pid = pids[0]
        os.kill(pid, signal.SIGINT)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            child = self.children.get(pid)
            if child is not None:
                child.poll()  # Reap an exited child so ps cannot see a zombie.
            if not self._processes(argv):
                return
            time.sleep(0.05)
        # Never silently hard-kill a process that may still own protected writes.
        raise HandbackRequired("Normal process shutdown did not finish")

    def stop_shop(self):
        self._stop(self.plan.shop_argv)
        if self._listener() is not None:
            raise TransitionRefused("Ordinary origin remains occupied")

    def stop_candidate(self):
        # Restricted profile's finally hook stops parent/detail and erases memory.
        self._stop(self.plan.candidate_argv)
        listener = self._listener()
        shop = self._processes(self.plan.shop_argv)
        if listener is not None and (not shop or listener != shop[0]):
            raise TransitionRefused("Unrecognized process prevents latest-state handback")

    def backup(self):
        self._process_state(require_shop=False)
        self._pointers()
        self._private_directory(self.backup_parent, create=True)
        destination = self.backup_parent / uuid.uuid4().hex
        destination.mkdir(mode=0o700)
        for path in self.plan.root.rglob("*"):
            relative = path.relative_to(self.plan.root)
            if path.is_symlink():
                raise TransitionRefused("Protected backup refuses symlinks")
            if any(part in BACKUP_EXCLUDED for part in relative.parts):
                continue
            target = destination / relative
            if path.is_dir():
                target.mkdir(mode=0o700, exist_ok=True)
            elif path.name in {"inventory.db-wal", "inventory.db-shm"}:
                continue
            elif relative == Path("inventory.db"):
                with (
                    sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as source,
                    sqlite3.connect(target) as backup,
                ):
                    source.backup(backup)
                os.chmod(target, 0o600)
            elif path.is_file():
                target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                shutil.copy2(path, target)
                os.chmod(target, 0o600)
            else:
                raise TransitionRefused("Unsupported protected backup entry")
        shutil.copy2(self.plan.startup_helper, destination / "saved-startup-helper.py")
        os.chmod(destination / "saved-startup-helper.py", 0o600)
        # Independent journals/revocations stay in their current sibling location.
        # Neither this backup nor handback writes or copies over those locations.
        return destination

    def _spawn(self, argv):
        if self._listener() is not None:
            raise TransitionRefused("Ordinary origin already occupied")
        environment = os.environ.copy()
        environment["DEX_PROFILE"] = "local"
        # Match the ordinary saved helper: private config owns these overrides.
        for name in ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_DELIVERY_POSTAL_CODE"):
            environment.pop(name, None)
        child = subprocess.Popen(
            argv,
            cwd=self.plan.root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.children[child.pid] = child
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise TransitionRefused("Selected runtime failed during startup")
            listener = self._listener()
            if listener == child.pid:
                with socket.create_connection((self.plan.host, self.plan.port), timeout=1):
                    return
            elif listener is not None:
                raise TransitionRefused("Unexpected ordinary-origin process during startup")
            time.sleep(0.05)
        raise TransitionRefused("Selected runtime startup deadline exceeded")

    def start_candidate(self):
        self.preflight(require_shop=False)
        self._spawn(self.plan.candidate_argv)

    def verify_handback(self):
        self.verify_handback_identity()
        self._pointers()
        self._compatible_shop_runtime()
        if self._processes(self.plan.candidate_argv):
            raise TransitionRefused("Candidate still active")
        shop = self._processes(self.plan.shop_argv)
        listener = self._listener()
        if listener is not None and (not shop or listener != shop[0]):
            raise TransitionRefused("Ordinary origin occupied by an unexpected process")

    def start_shop(self):
        self.verify_handback()
        if self._processes(self.plan.shop_argv):
            # A previous handback may have started SHOP before interruption.
            # Its exact process must already be serving; never start a duplicate.
            if self._listener() is None:
                raise HandbackRequired("Existing SHOP-04 process has not become ready")
            return
        self._spawn(self.plan.shop_argv)
