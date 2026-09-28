"""Two isolated Chromium contexts against the copied B1 app. Private output only.

Run with: uv run --with playwright python scripts/verify_b1_browser.py --root PRIVATE_ROOT
Requires Chrome installed locally. Never uses the owner's normal browser profile.
The target must have no authenticated accounts; this creates rehearsal accounts only.
"""

import argparse
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pokemon_hunter.beta.cli import setup

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
args = parser.parse_args()
os.umask(0o077)
setup(args.root)
from django.contrib.auth import get_user_model  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from pokemon_hunter.beta import accounts, store  # noqa: E402

assert not get_user_model().objects.exists(), "Use a fresh isolated B1 environment"
owner_password, member_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
owner = accounts.bootstrap(owner_password)
assert accounts.bootstrap(secrets.token_urlsafe(24)).pk == owner.pk
member = accounts.invite("rehearsal-collector")
invite = accounts.issue_link(member, "invite")
base = "http://127.0.0.1:8011"


def sign_in(page, username, password):
    page.goto(base + "/login/")
    page.get_by_label("Username:", exact=True).fill(username)
    page.get_by_label("Password:", exact=True).fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    try:
        page.wait_for_url(base + "/", timeout=8000)
    except Exception:
        (args.root / "browser-failure.txt").write_text(page.locator("body").inner_text())
        raise RuntimeError("Browser sign-in failed; private page diagnostic retained") from None


def add_synthetic_member_record():
    from django.db import connection

    actor = store.principal(member.pk)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO import_batches VALUES(%s,%s,%s,%s,%s)",
            ["browser-synthetic-batch", actor.user_id, "synthetic", "b1-check", "complete"],
        )
        cursor.execute(
            """INSERT INTO owned_copies(id,user_id,provisional_identity,batch_id,first_edition_selected,notes)
                          VALUES(%s,%s,%s,%s,0,%s)""",
            [
                "browser-synthetic-copy",
                actor.user_id,
                '{"synthetic":true}',
                "browser-synthetic-batch",
                "Synthetic adversarial test record",
            ],
        )
    connection.close()


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless=True
    )
    a, b = browser.new_context(), browser.new_context()
    pa, pb = a.new_page(), b.new_page()
    sign_in(pa, "admin", owner_password)
    pa.screenshot(path=str(args.root / "owner-collection.png"), full_page=False)
    pb.goto(base + invite)
    pb.get_by_label("New password:", exact=True).fill(member_password)
    pb.get_by_label("New password confirmation:", exact=True).fill(member_password)
    pb.get_by_role("button", name="Save password").click()
    sign_in(pb, "rehearsal-collector", member_password)
    assert pb.get_by_role("heading", name="Your collection is empty").is_visible()
    pb.screenshot(path=str(args.root / "member-empty.png"), full_page=False)
    owner_export = a.request.get(base + "/api/export/").json()
    copies = owner_export["copies"]
    assert len(copies) > 0
    assert b.request.get(base + "/api/export/?user_id=" + copies[0]["user_id"]).json()["copies"] == []
    assert b.request.get(base + "/api/hunts/").json()["hunts"] == []
    assert b.request.get(base + "/api/archives/").json()["archives"] == []
    assert b.request.get(base + "/api/inventory/" + copies[0]["id"] + "/").status == 404
    assert b.request.get(base + "/api/admin/catalog/").status == 403
    archives = a.request.get(base + "/api/archives/").json()["archives"]
    file = archives[0]
    assert b.request.get(base + "/files/" + file["batch_id"] + "/" + file["path"]).status == 404
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(add_synthetic_member_record).result()
    synthetic_url = base + "/api/inventory/browser-synthetic-copy/"
    assert b.request.get(synthetic_url).status == 200
    assert a.request.get(synthetic_url).status == 404
    assert "browser-synthetic-copy" not in {
        row["id"] for row in a.request.get(base + "/api/export/").json()["copies"]
    }
    csrf = next(cookie["value"] for cookie in a.cookies() if cookie["name"] == "dex_b1_csrf")
    assert (
        a.request.post(synthetic_url, form={"notes": "forbidden"}, headers={"X-CSRFToken": csrf}).status
        == 404
    )
    # Supported framework recovery in the browser; the link is never printed or persisted.
    with ThreadPoolExecutor(max_workers=1) as pool:
        recovery = pool.submit(accounts.issue_link, member, "recovery").result()
    pb.goto(base + "/")
    assert "/login/" in pb.url
    pb.goto(base + recovery)
    new_password = secrets.token_urlsafe(24)
    pb.get_by_label("New password:", exact=True).fill(new_password)
    pb.get_by_label("New password confirmation:", exact=True).fill(new_password)
    pb.get_by_role("button", name="Save password").click()
    sign_in(pb, "rehearsal-collector", new_password)
    pb.get_by_role("button", name="Sign out").click()
    pb.goto(base + "/")
    assert "/login/" in pb.url
    assert pa.get_by_role("heading", name="Your collection", exact=True).is_visible()
    report = {
        "independent_browser_contexts": 2,
        "owner_copies": len(copies),
        "owner_vintage_251": owner_export["vintage_251"],
        "member_copies": 0,
        "member_hunts": 0,
        "member_archives": 0,
        "cross_user_read_download_admin": "denied",
        "owner_access_to_member_synthetic_record": "read/write/export denied",
        "invite_recovery_logout": "passed in Chromium",
        "repeat_bootstrap": "same identity",
        "credentials": "random rehearsal-only, memory-only; no actual owner credential supplied",
        "browser_version": browser.version,
    }
    (args.root / "browser-report.json").write_text(json.dumps(report, indent=2) + "\n")
    browser.close()
print("Two-browser-session rehearsal passed; private report and screenshots saved.")
