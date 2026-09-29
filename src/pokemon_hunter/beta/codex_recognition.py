"""Local CLI transport. Authentication belongs exclusively to Codex, never Dex."""

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .diagnostics import failure as log_failure

MODEL = "gpt-5.6-sol"
TIMEOUT = 75
MAX_OUTPUT = 256_000


class RecognitionError(ValueError):
    """A fixed, safe user message; never include CLI stderr or credentials."""


def environment():
    # Do not pass API keys, app secrets, desktop session handles or provider overrides.
    return {k: os.environ[k] for k in ("HOME", "PATH", "CODEX_HOME", "TMPDIR") if k in os.environ}


def options(directory):
    values = {
        "approval_policy": "never",
        "forced_login_method": "chatgpt",
        "project_doc_max_bytes": 0,
        "skills.include_instructions": False,
        "skills.bundled.enabled": False,
        "web_search": "disabled",
        "mcp_servers": {},
        "plugins": {},
        "shell_environment_policy.inherit": "none",
        "model_reasoning_effort": "low",
        "model_provider": "dex_subscription",
        "model_providers.dex_subscription.name": "OpenAI",
        "model_providers.dex_subscription.requires_openai_auth": True,
        "model_providers.dex_subscription.wire_api": "responses",
        "model_providers.dex_subscription.request_max_retries": 0,
        "model_providers.dex_subscription.stream_max_retries": 0,
        "default_permissions": "dex_photo",
    }
    for feature in (
        "shell_tool",
        "unified_exec",
        "code_mode",
        "code_mode_host",
        "code_mode_only",
        "apps",
        "plugins",
        "hooks",
        "memories",
        "multi_agent",
        "multi_agent_v2",
        "browser_use",
        "browser_use_external",
        "browser_use_full_cdp_access",
        "computer_use",
        "in_app_browser",
        "image_generation",
        "goals",
        "shell_snapshot",
        "remote_plugin",
        "tool_suggest",
        "workspace_dependencies",
        "skill_mcp_dependency_install",
    ):
        values[f"features.{feature}"] = False
    args = []
    for key, value in values.items():
        # All values here are TOML-compatible JSON scalars or empty inline tables.
        args += ["-c", f"{key}={json.dumps(value)}"]
    args += [
        "-c",
        'permissions={dex_photo={filesystem={"/"="deny",'
        + json.dumps(str(directory))
        + '="read"},network={enabled=false}}}',
    ]
    return args


def terminate(process):
    # A separate session lets us terminate descendants as well as the CLI wrapper.
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        pass
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def failure(text):
    text = text.lower()
    if any(
        x in text
        for x in ("unexpected argument", "unknown variant", "error loading config", "not recognized")
    ):
        return (
            "Installed Codex CLI is incompatible with this recognition setup. Update it or choose manually."
        )
    if any(x in text for x in ("usage limit", "usage_limit", "rate limit", "rate_limit", "quota", "429")):
        return "Codex usage limit reached. Wait for capacity to reset or choose manually."
    if any(
        x in text
        for x in (
            "login",
            "authentication",
            "unauthorized",
            "401",
            "refresh token",
            "refresh_token",
            "sign in",
        )
    ):
        return "Codex login unavailable or expired. Sign in with codex login, then retry or choose manually."
    return "Codex recognition failed. Retry explicitly or choose manually."


def recognize(images, root, cancelled=lambda: False, job_id=None):
    from .scans import PROMPT, Clues

    start = time.monotonic()
    record = {
        "job_id": job_id,
        "provider": "codex_cli",
        "model": MODEL,
        "started": time.time(),
        "usage": None,
        "available_usage": None,
        "outcome": "failed",
        "submitted": False,
    }
    lock_fd = os.open(Path(root) / "codex-recognition.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RecognitionError(
                "Codex is already recognizing a photo. Retry or choose manually."
            ) from None
        binary = shutil.which("codex")
        if not binary:
            raise RecognitionError(
                "Codex CLI is missing from the server PATH. Install it or choose manually."
            )
        # mkdtemp is mode 0700; every payload file is explicitly 0600.
        with tempfile.TemporaryDirectory(prefix="dex-photo-") as temp:
            directory = Path(temp).resolve()

            def save(name, content):
                path = directory / name
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                return str(path)

            schema = save("schema.json", json.dumps(Clues.model_json_schema()).encode())
            output = save("result.json", b"")
            paths = [save(f"image-{i}.jpg", p) for i, p in enumerate(images)]
            args = [
                binary,
                "exec",
                "--ignore-user-config",
                "--ignore-rules",
                "--ephemeral",
                "--skip-git-repo-check",
                "--json",
                "--color",
                "never",
                "-C",
                str(directory),
                "--model",
                MODEL,
                "--output-schema",
                schema,
                "-o",
                output,
            ]
            args += options(directory)
            for path in paths:
                args += ["--image", path]
            args += [
                "--",
                PROMPT
                + "\nOnly inspect the attached images. No tools, files, inventory access or actions. Return only the requested JSON.",
            ]
            with (
                tempfile.TemporaryFile(dir=directory) as stdout,
                tempfile.TemporaryFile(dir=directory) as stderr,
            ):
                if cancelled():
                    record["outcome"] = "cancelled"
                    raise RecognitionError("Recognition cancelled. Choose manually to start again.")
                process = subprocess.Popen(
                    args,
                    cwd=directory,
                    env=environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=True,
                )
                record["submitted"] = True
                try:
                    while process.poll() is None:
                        if cancelled():
                            record["outcome"] = "cancelled"
                            raise RecognitionError("Recognition cancelled.")
                        if time.monotonic() - start > TIMEOUT:
                            record["outcome"] = "timeout"
                            raise RecognitionError(
                                "Codex recognition timed out. Retry explicitly or choose manually."
                            )
                        if max(stdout.tell(), stderr.tell(), Path(output).stat().st_size) > MAX_OUTPUT:
                            raise RecognitionError("Codex output exceeded its limit. Choose manually.")
                        time.sleep(0.1)
                finally:
                    terminate(process)
                stdout.seek(0)
                events = stdout.read(MAX_OUTPUT + 1)
                stderr.seek(0)
                errors = stderr.read(MAX_OUTPUT).decode(errors="replace")
                if len(events) > MAX_OUTPUT or Path(output).stat().st_size > MAX_OUTPUT:
                    raise RecognitionError("Codex output exceeded its limit. Choose manually.")
                completed = False
                for line in events.splitlines():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    if event.get("type") == "turn.completed":
                        completed = True
                        usage = event.get("usage") or {}
                        if not isinstance(usage, dict):
                            usage = {}
                        record["usage"] = {
                            k: v
                            for k, v in usage.items()
                            if k in {"input_tokens", "cached_input_tokens", "output_tokens"}
                            and type(v) is int
                            and v >= 0
                        }
                    if event.get("type") == "item.completed":
                        if event.get("item", {}).get("type") not in {"agent_message", "reasoning", "error"}:
                            raise RecognitionError("Codex attempted an unsupported action. Choose manually.")
                if process.returncode or not completed:
                    raise RecognitionError(failure(errors + events.decode(errors="replace")))
                try:
                    clues = Clues.model_validate_json(Path(output).read_bytes())
                except ValueError:
                    raise RecognitionError(
                        "Codex returned invalid card details. Retry or choose manually."
                    ) from None
                record["outcome"] = "completed"
                return clues, record["usage"]
    except OSError:
        raise RecognitionError(
            "Codex could not start. Check the CLI installation or choose manually."
        ) from None
    finally:
        original_error = sys.exc_info()[0] is not None
        try:
            record["latency"] = round(time.monotonic() - start, 3)
            fd = os.open(Path(root) / "codex-usage.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a") as log:
                fcntl.flock(log, fcntl.LOCK_EX)
                log.write(json.dumps(record) + "\n")
                log.flush()
                os.fsync(log.fileno())
        except OSError as exc:
            log_failure("codex_usage_write_failed", exc)
            if not original_error:
                raise RecognitionError(
                    "Recognition usage could not be saved; submission may have completed. "
                    "Choose manually and check local storage before retrying."
                ) from None
        finally:
            os.close(lock_fd)
