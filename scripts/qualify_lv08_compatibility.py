"""Rehearse a wheel transition and compatible rollback using generated state only.

Neither interpreter is changed. All application calls run isolated with provider
networking blocked. No customer root argument exists.
"""

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci import smoke

SETUP = """
import sys,json
from pathlib import Path
from pokemon_hunter.beta.cli import setup
root=Path(sys.argv[1]); assert (root/'SYNTHETIC_ONLY').is_file(); setup(root)
from django.contrib.auth import get_user_model
from pokemon_hunter.beta import store, readiness, hunter_policy, hunter_installed
actor=store.principal(get_user_model().objects.get(username='admin').pk)
"""
POLICY = """
from datetime import datetime,UTC,timedelta
from pokemon_hunter.beta import hunter, hunter_budget, discovery
hunter_policy.select(actor,dict(enabled=True,per_hunt_limit=5,daily_limit=5,
    timezone='America/New_York',recurring=False,
    expires_at=(datetime.now(UTC)+timedelta(days=1)).isoformat(),revision=0))
run=hunter.Run('lv08-authored-parent',(str(root),actor.user_id,'session'),
    discovery.Choices(),None,[],allowance=hunter_installed.current_allowance(actor))
hunter_policy.bind(run,actor)
hunter_budget.consume_traversal(root,run.id,'browse','auction',dispatch_id='one',
    allowance=run.allowance,scope='lots')
assert hunter_policy.status(actor)['used']==1
print(json.dumps(dict(package=hunter_installed.package_digest(),used=1)))
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authority(root):
    with closing(sqlite3.connect((root / "inventory.db").as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        rows = {}
        for name in names:
            if name.startswith(("sqlite_", "cr_", "ar_", "catalog_read_", "account_read_")):
                continue
            values = db.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall()
            rows[name] = hashlib.sha256(repr(sorted(values, key=repr)).encode()).hexdigest()
    return rows


def qualify(previous, candidate):
    report = {"status": "FAIL", "evidence_class": "generated isolated engineering", "checks": []}
    with tempfile.TemporaryDirectory(prefix="dex-lv08-transition-") as temporary:
        work = Path(temporary).resolve()
        home, cwd, root = work / "home", work / "cwd", work / "synthetic"
        home.mkdir()
        cwd.mkdir()
        env = smoke.isolated_environment(candidate, home)

        def invoke(python, code, arguments, phase):
            result = subprocess.run(
                [str(python), "-I", "-B", "-c", smoke.NETWORK_GUARD + code, *arguments],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=90,
            )
            if result.returncode:
                frames = re.findall(r'File "([^"]+)", line (\d+)', result.stderr)
                locations = [f"{Path(path).name}:{line}" for path, line in frames[-4:]]
                # No exception text, source lines or generated credentials enter the report.
                raise RuntimeError(f"{phase}: subprocess {result.returncode}; frames {locations}")
            return result.stdout

        def run(python, code, *args):
            return invoke(python, code, [str(root), *args], "isolated script")

        def operator(python, module, *args):
            return invoke(
                python,
                "import runpy,sys; module=sys.argv.pop(1); runpy.run_module(module,run_name='__main__')",
                ["pokemon_hunter.beta." + module, "--root", str(root), *args],
                module + " " + " ".join(args),
            )

        def prepare(python):
            operator(python, "catalog_read_operator", "migrate")
            operator(python, "account_read_operator", "migrate")
            build = json.loads(operator(python, "catalog_read_operator", "prepare"))["build"]
            operator(python, "catalog_read_operator", "activate", "--build", str(build))
            operator(python, "account_read_operator", "--username", "admin", "prepare")
            operator(python, "account_read_operator", "--username", "synthetic-member", "prepare")
            assert json.loads(operator(python, "catalog_read_operator", "status"))["ready"]
            assert json.loads(operator(python, "account_read_operator", "--username", "admin", "status"))[
                "ready"
            ]

        run(
            previous,
            "import runpy,sys;sys.argv=['synthetic','--output',sys.argv[1]];"
            "runpy.run_module('pokemon_hunter.beta.synthetic',run_name='__main__')",
        )
        run(
            previous,
            "import sys;from pathlib import Path;from pokemon_hunter.inventory import connect;"
            "from pokemon_hunter.beta.ownership_declarations import initialize;"
            "db=connect(Path(sys.argv[1])/'inventory.db');initialize(db);db.commit();db.close()",
        )
        prepare(previous)
        old = json.loads(run(previous, SETUP + POLICY))
        before = authority(root)
        secret = digest(root / "secret.key")
        usage = next(work.glob(".dex-shopping-discovery/*/everyday/hunter-usage.jsonl"))
        prefix = usage.read_bytes()
        report["previous_package_digest"] = old["package"]
        report["checks"].append("previous runtime prepared generated schema-2 state and consumed one attempt")
        run(candidate, SETUP + "assert not readiness.inspect(actor)['ready']")
        prepare(candidate)
        assert authority(root) == before and digest(root / "secret.key") == secret
        assert usage.read_bytes() == prefix
        report["checks"].append("candidate migration and both-account preparation preserve all authority")
        new = json.loads(
            run(
                candidate,
                SETUP + "assert readiness.inspect(actor)['ready']; "
                "assert hunter_policy.rebind_package(root,expected_previous=sys.argv[2],"
                "package_sha256=hunter_installed.package_digest()); "
                "assert hunter_policy.status(actor)['used']==1; "
                "print(json.dumps(dict(package=hunter_installed.package_digest())))",
                old["package"],
            )
        )
        report["candidate_package_digest"] = new["package"]
        assert usage.read_bytes().startswith(prefix)
        rebound = usage.read_bytes()
        run(previous, SETUP + "assert not readiness.inspect(actor)['ready']")
        report["checks"].append("old reader rejects successor policy/schema before rollback")
        operator(candidate, "account_read_operator", "retire-schema")
        assert authority(root) == before and usage.read_bytes() == rebound
        prepare(previous)
        run(
            previous,
            SETUP + "assert readiness.inspect(actor)['ready']; "
            "assert hunter_policy.rebind_package(root,expected_previous=sys.argv[2],"
            "package_sha256=hunter_installed.package_digest());"
            "assert hunter_policy.status(actor)['used']==1",
            new["package"],
        )
        assert authority(root) == before and digest(root / "secret.key") == secret
        assert usage.read_bytes().startswith(rebound)
        report["checks"].append(
            "rollback prepares previous policies with current authority and spent accounting"
        )
        prepare(candidate)
        run(candidate, SETUP + "assert readiness.inspect(actor)['ready']")
        assert authority(root) == before
        report["checks"].append("re-upgrade prepares current policies without restoration or reseeding")
        assert not (work / "network-attempts").exists()
        report.update(status="PASS", provider_calls=0, protected_authority_tables=len(before), consumed=1)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-python", type=Path, required=True)
    parser.add_argument("--candidate-python", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = qualify(args.previous_python.absolute(), args.candidate_python.absolute())
    except (Exception, subprocess.SubprocessError) as error:
        result = dict(status="FAIL", failure=type(error).__name__, reason=str(error))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"]}))
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
