"""Owned-resource failure tests; no provider or owner state access."""

import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pokemon_hunter.beta.diagnostics import closing


@pytest.mark.parametrize("primary", [None, ValueError("private primary"), KeyboardInterrupt()])
def test_cleanup_is_visible_and_preserves_active_errors(caplog, primary):
    class Resource:
        def close(self):
            raise OSError("SECRET cleanup")

    with pytest.raises(type(primary) if primary is not None else OSError) as caught:
        with closing(Resource(), "synthetic_close_failed"):
            if primary is not None:
                raise primary
    if primary is not None:
        assert caught.value is primary
    assert "synthetic_close_failed" in caplog.text
    assert "SECRET" not in caplog.text
    assert "private primary" not in caplog.text


def test_local_operator_failure_is_redacted(monkeypatch, caplog):
    from pokemon_hunter.beta import cli

    def broken():
        raise OSError("SECRET /private/owner.db")

    monkeypatch.setattr(cli, "main", broken)
    with pytest.raises(SystemExit) as caught:
        cli.entrypoint()
    assert caught.value.code != 0
    assert "local_operation_failed" in caplog.text
    assert "SECRET" not in str(caught.value) + caplog.text
    assert "/private/owner.db" not in str(caught.value) + caplog.text


@pytest.mark.parametrize("exit_code", [0, 1])
def test_scheduler_removal_reports_uncertain_stop(tmp_path, monkeypatch, capsys, exit_code):
    agent = tmp_path / "Library/LaunchAgents/local.pokemon-hunter.daily.plist"
    agent.parent.mkdir(parents=True)
    agent.write_text("synthetic schedule")
    calls = []

    def launchctl(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=exit_code, stderr=b"SECRET subprocess output")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(subprocess, "run", launchctl)
    monkeypatch.setattr(sys, "argv", ["schedule.py", "--remove"])
    script = Path(__file__).resolve().parents[1] / "scripts/schedule.py"
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(script), run_name="__main__")
    assert caught.value.code == 0
    assert not agent.exists()
    assert calls[0][1]["capture_output"] is True
    output = capsys.readouterr()
    assert ("stop was not confirmed" in output.err) is bool(exit_code)
    assert "does not confirm" in output.out
    assert "SECRET" not in output.out + output.err


@pytest.mark.parametrize("primary_kind", ["none", "provider", "stop", "cancel"])
def test_async_cleanup_preserves_primary_and_redacts(caplog, primary_kind):
    import asyncio

    from pokemon_hunter.beta.diagnostics import async_closing
    from pokemon_hunter.beta.discovery import _Stopped
    from pokemon_hunter.beta.discovery_transport import ProviderFailure

    primary = {
        "none": None,
        "provider": ProviderFailure("browse", status=503),
        "stop": _Stopped(),
        "cancel": asyncio.CancelledError("SECRET cancellation"),
    }[primary_kind]

    class Resource:
        async def close(self):
            raise OSError("SECRET cleanup /private/owner")

    async def acquire():
        async with async_closing(Resource(), "shopping_transport_close_failed"):
            if primary is not None:
                raise primary

    with pytest.raises(type(primary) if primary is not None else OSError) as caught:
        asyncio.run(acquire())
    if primary is not None:
        assert caught.value is primary
    assert "shopping_transport_close_failed" in caplog.text
    assert "SECRET" not in caplog.text
    assert "/private/owner" not in caplog.text


def test_async_cleanup_timeout_is_visible(caplog):
    import asyncio

    from pokemon_hunter.beta.diagnostics import async_closing

    cancelled = []

    class Resource:
        async def close(self):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

    async def acquire():
        async with async_closing(Resource(), "shopping_transport_close_failed", timeout=0.01):
            pass

    with pytest.raises(TimeoutError):
        asyncio.run(acquire())
    assert cancelled == [True]
    assert "shopping_transport_close_failed type=TimeoutError" in caplog.text


@pytest.mark.parametrize("component", ["discovery", "hunter", "listing_check", "hunter_lot_details"])
@pytest.mark.parametrize("kind", ["unexpected", "provider", "stop"])
def test_shopping_workers_observe_failures_without_private_text(monkeypatch, caplog, component, kind):
    import importlib

    from pokemon_hunter.beta import discovery as d
    from pokemon_hunter.beta.discovery_transport import ProviderFailure

    module = importlib.import_module("pokemon_hunter.beta." + component)
    event = {
        "discovery": "shopping_search_failed",
        "hunter": "hunter_acquisition_failed",
        "listing_check": "shopping_listing_failed",
        "hunter_lot_details": "hunter_lot_detail_failed",
    }[component]
    run = d.Run("synthetic", ("synthetic-root", "user", "session"), d.Choices(), None, [])
    # Hunter Run adds traversal fields; no catalog or database is involved here.
    run.traversal = None
    monkeypatch.setattr(module, "close_old_connections", lambda: None)
    monkeypatch.setattr(d.store, "verified", lambda actor: actor)
    monkeypatch.setattr(d, "_arm_deadline", lambda run: None)
    if component == "hunter":
        monkeypatch.setattr(module, "_clear_dependents", lambda run_id: None)

    async def broken(*args):
        if kind == "stop":
            run.cancel.set()
            raise d._Stopped
        if kind == "provider":
            raise ProviderFailure("browse", status=503)
        raise ValueError("SECRET provider payload /private/owner")

    monkeypatch.setattr(module, "_acquire", broken)
    actor = SimpleNamespace(user_id="user")
    args = (
        (run, actor, "session", ("fake", "fake"))
        if component == "hunter_lot_details"
        else (run, actor, ("fake", "fake"))
    )
    module._worker(*args)
    assert run.state == ("stopped" if kind == "stop" else "failed")
    assert not run.raws
    assert (event in caplog.text) is (kind != "stop")
    assert "SECRET" not in caplog.text + (run.error or "")
    assert "/private/owner" not in caplog.text + (run.error or "")


@pytest.mark.parametrize("component", ["discovery", "hunter", "listing_check", "hunter_lot_details"])
def test_acquisition_cleanup_keeps_provider_failure(monkeypatch, caplog, component):
    import asyncio
    import importlib

    from pokemon_hunter.beta import discovery as d
    from pokemon_hunter.beta import hunter
    from pokemon_hunter.beta.discovery_transport import ProviderFailure

    module = importlib.import_module("pokemon_hunter.beta." + component)
    original = ProviderFailure("oauth", status=401)
    closed = []

    class Fake:
        async def close(self):
            closed.append(True)
            raise OSError("SECRET cleanup")

    async def denied(*args):
        raise original

    monkeypatch.setattr(module, "Transport", Fake)
    monkeypatch.setattr(d, "access_token", denied)
    monkeypatch.setattr(d, "_arm_deadline", lambda run: None)
    monkeypatch.setattr(hunter, "_planned_lanes", lambda run: [])
    run = d.Run("synthetic", ("root", "user", "session"), d.Choices(), None, [])
    args = (
        (run, None, "session", ("fake", "fake"))
        if component == "hunter_lot_details"
        else (run, ("fake", "fake"))
    )
    with pytest.raises(ProviderFailure) as caught:
        asyncio.run(module._acquire(*args))
    assert caught.value is original
    assert closed == [True]
    assert "shopping_transport_close_failed" in caplog.text
    assert "SECRET" not in caplog.text


def test_response_cleanup_keeps_http_failure(monkeypatch, caplog):
    import asyncio

    import httpx

    from pokemon_hunter.beta.discovery_transport import ProviderFailure, Transport

    class BrokenStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"SECRET response"

        async def aclose(self):
            raise OSError("SECRET response cleanup")

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(503, stream=BrokenStream())

    async def acquire():
        transport = Transport(transport=httpx.MockTransport(respond))
        try:
            await transport.request("oauth", timeout=1, credentials=("fake", "fake"))
        finally:
            await transport.close()

    with pytest.raises(ProviderFailure) as caught:
        asyncio.run(acquire())
    assert caught.value.status == 503
    assert len(calls) == 1
    assert "shopping_response_close_failed" in caplog.text
    assert "SECRET" not in caplog.text


def test_dispatch_cancellation_is_uncertain_and_late_failure_is_consumed(monkeypatch, caplog):
    import asyncio
    import time

    from pokemon_hunter.beta import discovery as d

    records = []
    monkeypatch.setattr(d, "_journal", lambda run, stage, state, **kw: records.append((state, kw)))

    async def scenario():
        started, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        unhandled = []
        asyncio.get_running_loop().set_exception_handler(lambda loop, context: unhandled.append(context))

        class Transport:
            async def request(self, *args, **kwargs):
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    await release.wait()
                    raise OSError("SECRET late provider outcome")

        run = d.Run("synthetic", ("root", "user", "session"), d.Choices(), None, [])
        dispatch = asyncio.create_task(d._dispatch(run, Transport(), "oauth", time.monotonic() + 5))
        await started.wait()
        dispatch.cancel()
        await cancelled.wait()
        with pytest.raises(asyncio.CancelledError):
            await dispatch
        release.set()
        # Let the pending transport and result callback finish in this loop.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not unhandled
        assert run.counts["oauth"] == run.counts["total"] == 1

    asyncio.run(scenario())
    assert records[-1] == ("uncertain", {"attempt": 1, "reason": "cancelled_in_flight"})
    assert "SECRET" not in caplog.text
