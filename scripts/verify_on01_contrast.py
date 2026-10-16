"""Focused installed-package styling regression. Disposable engineering state only."""

import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[1]
MEASURE = r"""selectors => {
 const rgb=s=>s.match(/[\d.]+/g).map(Number);
 const luminance=c=>c.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4}).reduce((v,x,i)=>v+x*[.2126,.7152,.0722][i],0);
 const result={};
 for(const [name,selector] of Object.entries(selectors)){
  const e=document.querySelector(selector),s=getComputedStyle(e);let bg=[0,0,0,0];
  for(let n=e;n;n=n.parentElement){const c=rgb(getComputedStyle(n).backgroundColor);const a=c[3]??1;
   bg=[...bg.slice(0,3).map((x,i)=>x+c[i]*a*(1-bg[3])),bg[3]+a*(1-bg[3])];if(bg[3]>=1)break;}
  bg=bg.slice(0,3).map(x=>x+255*(1-bg[3]));const a=luminance(rgb(s.color)),b=luminance(bg);
  result[name]={color:s.color,background: bg,contrast:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),font:parseFloat(s.fontSize),backgroundColor:s.backgroundColor,outlineColor:s.outlineColor,outlineWidth:s.outlineWidth,outlineStyle:s.outlineStyle,outlineOffset:s.outlineOffset,outlineContrast:(Math.max(luminance(rgb(s.outlineColor)),b)+.05)/(Math.min(luminance(rgb(s.outlineColor)),b)+.05),textDecoration:s.textDecorationLine,rect:JSON.parse(JSON.stringify(e.getBoundingClientRect()))};
 }return result;
}"""
SELECTORS = dict(
    title="#bulk-entry h1", introduction="#bulk-entry > :first-child p", back="#bulk-entry > :first-child a"
)
NAV = dict(header="header.app-header", link="header.app-header nav a")
PREPARE = """
import sys
from pathlib import Path
import pokemon_hunter
assert Path(pokemon_hunter.__file__).is_relative_to(Path(sys.prefix))
from pokemon_hunter.beta.cli import setup
setup(Path(sys.argv[1]))
from pokemon_hunter.beta import collection_drafts
collection_drafts.initialize()
print(pokemon_hunter.__file__)
"""


def run(args):
    from playwright.sync_api import expect, sync_playwright

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(
        evidence_class="disposable installed-package engineering browser; no customer state",
        python=str(args.python),
        provider_operations=0,
        states=[],
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("DEX_", "EBAY_", "OPENAI_", "POKEMON_HUNTER_", "PYTHONPATH"))
        and k != "DATABASE_URL"
    }
    env.update(
        DEX_PROFILE="local", PLAYWRIGHT_BROWSERS_PATH=str(Path.home() / "Library/Caches/ms-playwright")
    )
    with tempfile.TemporaryDirectory(prefix="dex-heading-engineering-") as temp:
        tmp = Path(temp)
        root = tmp / "synthetic"
        env["HOME"] = str(tmp)
        subprocess.run(
            [str(args.python), "-I", "-m", "pokemon_hunter.beta.synthetic", "--output", str(root)],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        result["package_origin"] = subprocess.check_output(
            [str(args.python), "-I", "-c", PREPARE, str(root)], cwd=tmp, env=env, text=True
        ).strip()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
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
                cwd=tmp,
                env=env,
                stdout=log,
                stderr=log,
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
                    requests = []
                    context.on("page", lambda p: p.on("pageerror", lambda e: errors.append(str(e))))
                    context.route(
                        "**/*", lambda r: r.continue_() if r.request.url.startswith(base + "/") else r.abort()
                    )
                    page = context.new_page()
                    page.goto(base + "/login/")
                    page.get_by_label("Username:", exact=True).fill("admin")
                    page.get_by_label("Password:", exact=True).fill(
                        json.loads((root / "credentials.json").read_text())["admin"]
                    )
                    page.get_by_role("button", name="Sign in", exact=True).click()
                    page.wait_for_url(lambda url: "/login/" not in url)
                    page.goto(base + "/add-card/")
                    result["neighbor_before"] = page.evaluate(MEASURE, dict(title="main h1", **NAV))
                    page.screenshot(path=str(output / "neighbor-before.png"))
                    page.goto(base + "/add-many/")
                    expect(page.locator("#bulk-status")).to_contain_text("Select cards")
                    context.on(
                        "request",
                        lambda r: requests.append(dict(method=r.method, url=r.url.removeprefix(base))),
                    )
                    for width in (1280, 390, 320):
                        for doubled in (False, True):
                            page.set_viewport_size(dict(width=width, height=900))
                            page.reload()
                            expect(page.locator("#bulk-status")).to_contain_text("Select cards")
                            nav_before = page.evaluate(MEASURE, NAV)
                            fonts = page.evaluate(
                                """() => Object.fromEntries([...document.querySelectorAll('#bulk-entry h1,#bulk-entry > :first-child p,#bulk-entry > :first-child a')].map(e=>[e.tagName,parseFloat(getComputedStyle(e).fontSize)]))"""
                            )
                            if doubled:
                                page.evaluate(
                                    """() => {const nodes=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const [e,n] of nodes)e.style.fontSize=(2*n)+'px';}"""
                                )
                            styles = page.evaluate(MEASURE, SELECTORS)
                            for name, tag in [("title", "H1"), ("introduction", "P"), ("back", "A")]:
                                assert styles[name]["font"] == fonts[tag] * (2 if doubled else 1)
                                if not args.expect_defect:
                                    assert styles[name]["contrast"] >= 4.5, styles
                            overflow = page.evaluate("document.documentElement.scrollWidth>innerWidth")
                            if not args.expect_defect:
                                assert not overflow
                            link = page.locator("#bulk-entry > :first-child a")
                            # Reach focus by actual keyboard navigation, not an artificial outline class.
                            link.focus()
                            page.keyboard.press("Tab")
                            page.keyboard.press("Shift+Tab")
                            assert link.evaluate(
                                'e=>e===document.activeElement && e.matches(":focus-visible")'
                            )
                            focused = page.evaluate(MEASURE, dict(back=SELECTORS["back"]))["back"]
                            assert (
                                focused["outlineStyle"] == "solid"
                                and float(focused["outlineWidth"][:-2]) >= 3
                            )
                            page.screenshot(
                                path=str(output / f"entry-{width}-{200 if doubled else 100}-focus.png")
                            )
                            link.hover()
                            hover = page.evaluate(MEASURE, dict(back=SELECTORS["back"]))["back"]
                            if not args.expect_defect:
                                assert hover["contrast"] >= 4.5 and hover["textDecoration"] == "underline"
                            result["states"].append(
                                dict(
                                    width=width,
                                    text_percent=200 if doubled else 100,
                                    original_fonts=fonts,
                                    styles=styles,
                                    focus=focused,
                                    hover=hover,
                                    overflow=overflow,
                                    nav=nav_before,
                                )
                            )
                    page.set_viewport_size(dict(width=1280, height=900))
                    page.reload()
                    page.locator("#bulk-entry > :first-child a").click()
                    expect(page).to_have_url(base + "/add-card/")
                    result["neighbor_after"] = page.evaluate(MEASURE, dict(title="main h1", **NAV))
                    assert result["neighbor_before"] == result["neighbor_after"]
                    page.screenshot(path=str(output / "neighbor-after.png"))
                    page.get_by_role("link", name="Open manual bulk entry", exact=True).click()
                    expect(page).to_have_url(base + "/add-many/")
                    result["back_and_return"] = True
                    result["bulk_header_count"] = page.locator("#bulk-entry header").count()
                    if not args.expect_defect:
                        assert result["bulk_header_count"] == 0
                    result["browser_errors"] = errors
                    assert not errors
                    result["read_only_entry_requests"] = requests
                    assert all(r["method"] == "GET" for r in requests)
                    browser.close()
                assert json.loads((output / "provider-calls.json").read_text())["calls"] == 0
                result["status"] = "EXPECTED_DEFECT" if args.expect_defect else "PASS"
            finally:
                server.terminate()
                server.wait(timeout=15)
    (output / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(status=result["status"], states=len(result["states"]), provider_operations=0)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-defect", action="store_true")
    run(parser.parse_args())
