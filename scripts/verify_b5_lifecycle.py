"""Local subprocess web/worker restart and cooperative termination, with staged configuration."""

import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from pokemon_hunter.beta import deployment

deployment.setup()
from pokemon_hunter.beta import support  # noqa: E402

before = support.diagnostics()["recognition"]["reserved_usd"]
env = dict(os.environ, PORT="18001")
command = [sys.executable, "-m", "pokemon_hunter.beta.deployment"]


def health():
    req = Request(
        "http://127.0.0.1:18001/healthz/",
        headers={"Host": env["DEX_PUBLIC_ORIGIN"].removeprefix("https://"), "X-Forwarded-Proto": "https"},
    )
    try:
        with urlopen(req, timeout=2) as response:
            return json.load(response)["ready"]
    except OSError:
        return False


for attempt in range(2):
    worker = subprocess.Popen(
        command + ["worker"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    web = subprocess.Popen(command + ["web"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if health():
                break
            time.sleep(0.1)
        assert health() and worker.poll() is None and web.poll() is None
        worker.terminate()
        assert worker.wait(timeout=5) == 0
        web.terminate()
        assert web.wait(timeout=5) in (0, -15)  # Uvicorn re-raises handled SIGTERM after shutdown.
    finally:
        for process in (worker, web):
            if process.poll() is None:
                process.kill()
                process.wait()
assert support.diagnostics()["recognition"]["reserved_usd"] == before
print(
    json.dumps(
        {"web_worker_restart_twice": "PASS", "SIGTERM_clean_exit": "PASS", "reservation_sum_preserved": True}
    )
)
