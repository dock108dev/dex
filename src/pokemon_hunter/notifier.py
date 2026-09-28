import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx

from .models import Listing


def digest_text(items: list[Listing], now: datetime, collection: str) -> str:
    high = sum(x.priority == "high" for x in items)
    medium = sum(x.priority == "medium" for x in items)
    lines = [
        f"{len(items)} Pokémon lot hits · {high} HIGH · {medium} MEDIUM",
        collection,
        "USD · Shipping included · Sales tax excluded · Seller claims unverified",
        "",
    ]
    for item in items:
        lines += [
            f"{item.priority.upper()} — {item.title}",
            f"{item.count.denominator} cards · {'Auction current bid' if item.listing_type == 'auction' else 'Buy It Now'}",
            f"${item.item_price:.2f} + ${item.shipping_price:.2f} shipping = ${item.landed_price:.2f}",
            f"${item.cost_per_card:.3f}/card delivered · {item.purity.replace('_', ' ')}",
        ]
        if item.listing_type == "auction":
            minutes = max(0, int((item.end_time - now).total_seconds() / 60))
            lines += [
                f"Ends in {minutes // 60}h {minutes % 60}m · Bids: {item.bid_count if item.bid_count is not None else 'unknown'}",
                f"Max bid under card-price and spend limits: ${item.max_bid:.2f}",
                "Daily snapshot; current bid and shipping may change.",
            ]
        lines += [
            "Sets: "
            + (
                ", ".join(s.replace("_", " ").title() for s in sorted(item.detected_sets))
                or "Unspecified vintage"
            )
        ]
        if item.excluded_sets:
            lines += ["Other detected: " + ", ".join(sorted(item.excluded_sets))]
        lines += ["Why: " + " · ".join(item.reasons), item.url, ""]
    return "\n".join(lines)


class Notifier:
    def __init__(self, directory: Path, webhook: str | None = None, macos: bool = False):
        self.directory = directory
        self.webhook = webhook
        self.macos = macos
        if webhook and not webhook.startswith("https://"):
            raise ValueError("Notification webhook must use HTTPS")
        if macos and sys.platform != "darwin":
            raise ValueError("macOS notifications require macOS")

    def send(self, digest_id: str, body: str):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{digest_id}.txt"
        temp = path.with_suffix(".tmp")
        temp.write_text(body + "\n")
        temp.replace(path)
        if self.webhook:
            try:
                response = httpx.post(
                    self.webhook,
                    json={"text": body},
                    headers={"Idempotency-Key": digest_id},
                    timeout=30,
                    follow_redirects=False,
                )
                if not 200 <= response.status_code < 300:
                    raise RuntimeError(f"Notification endpoint returned HTTP {response.status_code}")
            except httpx.TransportError:
                raise RuntimeError("Notification delivery failed; digest retained for retry") from None
        if self.macos:
            # Pass content as argv, never interpolate seller text into AppleScript.
            script = 'on run argv\ndisplay notification (item 1 of argv) with title "Pokémon Hunter"\nend run'
            subprocess.run(
                ["osascript", "-e", script, body.splitlines()[0] + "\n" + str(path)],
                check=True,
                capture_output=True,
                timeout=15,
            )
        latest = self.directory / "latest.txt"
        temp = latest.with_suffix(".tmp")
        temp.write_text(body + "\n")
        temp.replace(latest)
        return path


def from_settings(directory, settings):
    return Notifier(
        directory, os.getenv("POKEMON_HUNTER_WEBHOOK_URL") or None, settings.alerts.macos_notification
    )
