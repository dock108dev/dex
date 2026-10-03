#!/usr/bin/env python3
"""Generate or install a macOS daily LaunchAgent using absolute paths."""

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--hour", type=int, default=8)
parser.add_argument("--minute", type=int, default=0)
parser.add_argument("--install", action="store_true")
parser.add_argument("--remove", action="store_true")
args = parser.parse_args()
if not 0 <= args.hour <= 23 or not 0 <= args.minute <= 59:
    parser.error("Use a valid local time")
root = Path(__file__).resolve().parents[1]
label = "local.pokemon-hunter.daily"
agent = Path.home() / "Library/LaunchAgents" / f"{label}.plist"


def stop_agent():
    # An unloaded agent is non-fatal, but a nonzero exit cannot prove it stopped.
    result = subprocess.run(
        ["launchctl", "bootout", f"gui/{os.getuid()}", str(agent)], check=False, capture_output=True
    )
    if result.returncode:
        print(
            f"LaunchAgent stop was not confirmed (exit {result.returncode}). Check its state before assuming the watcher stopped.",
            file=sys.stderr,
        )


if args.remove:
    if agent.exists():
        stop_agent()
        agent.unlink()
    print("Daily schedule file removed. This does not confirm an in-flight watcher stopped.")
    raise SystemExit(0)
python = root / ".venv/bin/python"
plist = {
    "Label": label,
    "ProgramArguments": [str(python), "-m", "pokemon_hunter.main", "--root", str(root), "run"],
    "WorkingDirectory": str(root),
    "StartCalendarInterval": {"Hour": args.hour, "Minute": args.minute},
    "StandardOutPath": str(root / "data/daily.log"),
    "StandardErrorPath": str(root / "data/daily-error.log"),
    "ProcessType": "Background",
}
output = root / "deploy" / f"{label}.plist"
output.parent.mkdir(exist_ok=True)
output.write_bytes(plistlib.dumps(plist))
if args.install:
    if sys.platform != "darwin":
        parser.error("LaunchAgent installation requires macOS; see README for cron")
    result = subprocess.run([str(python), "-m", "pokemon_hunter.main", "--root", str(root), "doctor"])
    if result.returncode:
        raise SystemExit("Daily schedule not installed: finish the missing local setup first.")
    agent.parent.mkdir(parents=True, exist_ok=True)
    if agent.exists():
        stop_agent()
    agent.write_bytes(output.read_bytes())
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(agent)], check=True)
    print(f"Daily watcher installed for {args.hour:02}:{args.minute:02} local time.")
else:
    print(f"Generated {output}; not installed. Use --install after configuring credentials.")
