"""Opt-in isolated engineering evidence; never acceptance or customer telemetry."""

import functools
import hashlib
import json
import os
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

OUT = Path(os.environ.get("DEX_GOAL_DIAGNOSTIC_OUT", "reports/ci/bulk-goal"))
TARGET = "test_custom_goal_keeps_members_and_labels_across_search_and_pages[bulk]"
active = False
lock = threading.Lock()
restores = []
page_ref = None
confirm_entered = threading.Event()
confirm_release = threading.Event()
confirm_done = threading.Event()


def emit(event, **fields):
    if not active:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    with lock, (OUT / "transitions.jsonl").open("a") as stream:
        stream.write(
            json.dumps(
                dict(
                    event=event,
                    time_ns=time.time_ns(),
                    monotonic_ns=time.monotonic_ns(),
                    thread=threading.get_ident(),
                    **fields,
                ),
                default=str,
            )
            + "\n"
        )


def state(actor):
    from pokemon_hunter.beta import account_read_build as builds
    from pokemon_hunter.beta import store

    try:
        return dict(
            authority=builds.authority(actor),
            account=store.rows(
                "SELECT generation,revision,catalog_token,status,seal FROM account_read_state WHERE user_id=%s",
                [actor.user_id],
            ),
            catalog=store.rows(
                "SELECT a.build,b.revision,b.status,b.seal FROM catalog_read_active a JOIN catalog_read_builds b ON a.build=b.id"
            ),
        )
    except Exception as error:
        return {"unavailable_state_type": type(error).__name__}


def wrap(module, name):
    original = getattr(module, name)

    @functools.wraps(original)
    def observed(actor, *args, **kwargs):
        if not active:
            return original(actor, *args, **kwargs)
        emit(
            name + ".before",
            state=state(actor),
            requested={
                k: v for k, v in kwargs.items() if k in ("requested_generation", "requested_revision")
            },
        )
        controlled = name == "confirm" and os.environ.get("DEX_GOAL_CONTROLLED") == "1"
        if controlled:
            confirm_entered.set()
            emit("confirm.paused")
            confirm_release.wait(2)
        try:
            result = original(actor, *args, **kwargs)
        except Exception as error:
            emit(
                name + ".error",
                error_type=type(error).__name__,
                message_hash=hashlib.sha256(str(error).encode()).hexdigest(),
                frames=[
                    dict(file=Path(f.filename).name, line=f.lineno, function=f.name)
                    for f in traceback.extract_tb(error.__traceback__)
                ],
            )
            raise
        if controlled:
            confirm_done.set()
        safe = {
            k: result[k]
            for k in ("id", "kind", "state", "generation", "user_id")
            if isinstance(result, dict) and k in result
        }
        if isinstance(result, dict) and "changes" in result:
            safe["changes_hash"] = hashlib.sha256(
                json.dumps(result["changes"], sort_keys=True).encode()
            ).hexdigest()
        emit(name + ".after", state=state(actor), receipt=safe, previous_present=result is not None)
        return result

    setattr(module, name, observed)
    restores.append((module, name, original))


def pytest_sessionstart(session):
    from pokemon_hunter.beta import account_read_build as builds
    from pokemon_hunter.beta import collection

    for module, name in [
        (collection, "preview"),
        (collection, "confirm"),
        (builds, "before_mutation"),
        (builds, "_refresh"),
        (builds, "refresh"),
        (builds, "prepare"),
        (builds, "state"),
    ]:
        wrap(module, name)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global active
    active = item.nodeid.endswith(TARGET)
    emit("test.start", nodeid=item.nodeid)


@pytest.hookimpl(wrapper=True)
def pytest_fixture_setup(fixturedef, request):
    global page_ref
    result = yield
    if active and fixturedef.argname == "browser_app":
        actor, page, base, _, _ = result
        page_ref = page
        if os.environ.get("DEX_GOAL_CONTROLLED") == "1":

            def release_on_stale_read(route):
                if confirm_entered.is_set() and not confirm_done.is_set():
                    emit(
                        "goal.read.held.until.commit",
                        selectors={
                            k: v
                            for k, v in parse_qs(urlsplit(route.request.url).query).items()
                            if k in ("generation", "account_revision", "catalog_revision")
                        },
                    )
                    confirm_release.set()
                    if not confirm_done.wait(10):
                        raise AssertionError("Controlled confirmation did not complete")
                route.continue_()

            page.route(base + "/api/v2/goals/**", release_on_stale_read)

        emit("browser.fixture.ready", state=state(actor["actor"]))
        page.on(
            "request",
            lambda r: emit(
                "request",
                method=r.method,
                path=urlsplit(r.url).path,
                selectors={
                    k: v
                    for k, v in parse_qs(urlsplit(r.url).query).items()
                    if k in ("generation", "account_revision", "catalog_revision")
                },
            ),
        )
        page.on(
            "requestfailed", lambda r: emit("request.failed", path=urlsplit(r.url).path, failure=r.failure)
        )
        page.on("response", lambda r: emit("response", path=urlsplit(r.url).path, status=r.status))
        page.on(
            "console",
            lambda msg: (
                emit("browser.state", record=json.loads(msg.text[11:]))
                if msg.text.startswith("GOAL_TRACE:")
                else None
            ),
        )
        page.add_init_script("""(() => {
          const record=(event,extra={})=>console.log('GOAL_TRACE:'+JSON.stringify({event,at:Date.now(),...extra,authority:typeof data==='undefined'?null:{read_state:data.read_state,generation:data.effective_collection?.generation},operation:typeof currentOperation==='undefined'?null:{id:currentOperation?.id,state:currentOperation?.state}}));
          const original=window.fetch;
          window.fetch=async function(input,options){const path=new URL(typeof input==='string'?input:input.url,location.href).pathname;record('fetch.start',{path});options?.signal?.addEventListener('abort',()=>record('fetch.abort',{path}),{once:true});try{const response=await original.apply(this,arguments);record('fetch.response',{path,status:response.status});return response;}catch(error){record('fetch.error',{path,name:error.name});throw error;}};
          addEventListener('pagehide',()=>record('pagehide'));
          addEventListener('click',e=>{if(e.target.closest('#confirm,[data-close="review"]'))record('review.click',{confirm:!!e.target.closest('#confirm')});},true);
        })();""")
    return result


def pytest_runtest_teardown(item):
    if active and page_ref is not None:
        try:
            emit(
                "browser.final",
                body_hash=hashlib.sha256(page_ref.locator("body").inner_text().encode()).hexdigest(),
                checklist_buttons=page_ref.locator("[data-checklist]").count(),
            )
        except Exception as error:
            emit("browser.final.error", error_type=type(error).__name__)


def pytest_collection_modifyitems(items):
    if os.environ.get("DEX_GOAL_PREFIX") == "1":
        index = next(i for i, item in enumerate(items) if item.nodeid.endswith(TARGET))
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "selection.json").write_text(
            json.dumps(
                {
                    "diagnostic_only": True,
                    "selected": [x.nodeid for x in items[: index + 1]],
                    "not_executed_after_target": len(items) - index - 1,
                },
                indent=2,
            )
        )
        del items[index + 1 :]


def pytest_sessionfinish(session, exitstatus):
    for module, name, original in reversed(restores):
        setattr(module, name, original)
