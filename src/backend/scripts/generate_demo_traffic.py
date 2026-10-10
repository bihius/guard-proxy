"""Populate the log ingest API with explicitly synthetic screenshot events.

This does not send requests through HAProxy or measure actual WAF decisions.
The live mode runs for a bounded time and adds varied, clearly synthetic chart data.
"""

import argparse
import json
import os
import random
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


class NoRedirect(HTTPRedirectHandler):
    """Keep ingest credentials and events on the explicitly selected origin."""

    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str,
        headers: object, newurl: str,
    ) -> None:
        return None


DEFAULT_HOSTS = ("shop.example.test", "api.example.test", "portal.example.test")
SOURCE_IPS = ("192.0.2.19", "198.51.100.42", "203.0.113.77", "2001:db8::5")
ATTACKS = (
    ("SQL injection", 942100, "/products?id=1%27%20OR%20%271%27%3D%271", "critical"),
    ("Cross-site scripting", 941100,
     "/search?q=%3Cscript%3Ealert(1)%3C/script%3E", "error"),
    ("Local file inclusion", 930100, "/download?file=../../etc/passwd", "error"),
    ("Scanner detection", 913100, "/admin/login", "warning"),
)

def _event(
    index: int,
    run_id: str,
    at: datetime,
    host: str,
    attack: tuple[str, int, str, str],
    action: str,
    source_ip: str,
) -> dict[str, object]:
    label, rule_id, uri, severity = attack
    return {
        "producer_event_id": f"demo:{run_id}:{index}",
        "event_at": at.isoformat(),
        "vhost": host,
        "action": action,
        "source_ip": source_ip,
        "method": "GET",
        "request_uri": uri,
        "status_code": 403 if action == "deny" else 200,
        "rule_id": rule_id,
        "rule_message": f"Demo: {label}",
        "anomaly_score": 10 if action == "deny" else 3,
        "severity": severity if action == "deny" else "warning",
        "message": "Synthetic screenshot event — not an observed WAF decision",
        "raw_context": {"synthetic": True, "purpose": "dashboard screenshot"},
    }


def generate_events(
    count: int,
    hours: float,
    hosts: tuple[str, ...],
    now: datetime,
    run_id: str,
    seed: int = 42,
) -> list[dict[str, object]]:
    """Spread predictable demo events across hours, including recent activity."""
    if count < 1 or hours <= 0 or hours > 29 * 24 or not hosts:
        raise ValueError("count and hosts must be nonempty; hours must be in (0, 696]")
    rng = random.Random(seed)
    events: list[dict[str, object]] = []
    for index in range(count):
        action = ("deny", "deny", "deny", "monitor", "allow")[index % 5]
        # The first events are always recent; the rest cover the selected window.
        age = (index * hours * 3600 / count) if index >= 5 else index * 45
        age += rng.uniform(0, min(30, hours * 3600 / count))
        events.append(
            _event(
                index, run_id, now - timedelta(seconds=age),
                hosts[index % len(hosts)], ATTACKS[index % len(ATTACKS)],
                action, SOURCE_IPS[index % len(SOURCE_IPS)],
            )
        )
    return events

def random_events(
    count: int,
    hosts: tuple[str, ...],
    start: datetime,
    end: datetime,
    run_id: str,
    first_index: int,
    rng: random.Random,
) -> list[dict[str, object]]:
    """Create synthetic requests with randomized times, targets and actions."""
    span = (end - start).total_seconds()
    return [
        _event(
            first_index + index, run_id,
            start + timedelta(seconds=rng.uniform(0, span)),
            rng.choice(hosts), rng.choice(ATTACKS),
            rng.choice(("deny", "deny", "deny", "monitor", "allow")),
            rng.choice(SOURCE_IPS),
        )
        for index in range(count)
    ]


def run_live(
    duration_seconds: float,
    hosts: tuple[str, ...],
    run_id: str,
    send: Callable[[list[dict[str, object]]], int],
    *,
    rng: random.Random,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    clock: Callable[[], float] = time.monotonic,
    wait: Callable[[float], None] = time.sleep,
    interval_seconds: float = 60,
) -> None:
    """Seed uneven chart history, then send random batches until the deadline."""
    deadline = clock() + duration_seconds
    index = 0
    started_at = now()
    # The default dashboard spans 24 hours; its bars are one hour wide.
    for hours_ago in range(23, 0, -1):
        end = started_at - timedelta(hours=hours_ago)
        batch = random_events(
            rng.randint(3, 18), hosts, end - timedelta(hours=1),
            end, run_id, index, rng,
        )
        send(batch)
        index += len(batch)
    # The 1h view uses five-minute buckets.
    for bucket in range(11, -1, -1):
        end = started_at - timedelta(minutes=5 * bucket)
        batch = random_events(
            rng.randint(2, 10), hosts, end - timedelta(minutes=5),
            end, run_id, index, rng,
        )
        send(batch)
        index += len(batch)
    while clock() < deadline:
        batch = random_events(
            rng.randint(4, 24), hosts, now() - timedelta(seconds=30),
            now(), run_id, index, rng,
        )
        send(batch)
        index += len(batch)
        print(f"Live demo: {index} synthetic events accepted", flush=True)
        wait(min(interval_seconds, max(0, deadline - clock())))
    print(f"Live demo finished after {duration_seconds:g}s ({index} events)", flush=True)


def post_events(
    events: list[dict[str, object]], url: str, route_host: str, secret: str,
) -> int:
    """Send synthetic events to the demo ingest endpoint only."""
    opener = build_opener(NoRedirect)
    created = 0
    for index, event in enumerate(events, 1):
        request = Request(
            url,
            data=json.dumps(event).encode(),
            headers={
                "Content-Type": "application/json",
                "Host": route_host,
                "X-Guard-Proxy-Ingest-Secret": secret,
            },
            method="POST",
        )
        try:
            with opener.open(request, timeout=10) as response:
                if response.status not in (200, 201):
                    raise RuntimeError(f"event {index}: unexpected HTTP {response.status}")
                created += response.status == 201
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"event {index}/{len(events)}: {exc}") from exc
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8080", help="HAProxy origin")
    parser.add_argument(
        "--route-host", default="app.local", help="Existing HAProxy vhost routing to the API"
    )
    parser.add_argument(
        "--hosts", nargs="+", default=DEFAULT_HOSTS, help="Display hostnames (synthetic)"
    )
    parser.add_argument("--count", type=int, default=240)
    parser.add_argument("--hours", type=float, default=48)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--run-id", default=None, help="Repeat this ID to avoid duplicate inserts")
    parser.add_argument("--dry-run", action="store_true", help="Print sample events without posting")
    parser.add_argument(
        "--live-minutes", type=float, metavar="MINUTES",
        help="send random batches every minute for up to one hour, seeding uneven 1h/24h charts",
    )
    args = parser.parse_args()
    if args.run_id and (len(args.run_id) > 100 or not args.run_id.isascii()):
        parser.error("run-id must be at most 100 ASCII characters")
    run_id = args.run_id or uuid4().hex
    if args.live_minutes is not None and not 0 < args.live_minutes <= 60:
        parser.error("--live-minutes must be in (0, 60]")
    if args.count < 1 or not 0 < args.hours <= 29 * 24:
        parser.error("count must be positive and hours must be in (0, 696]")
    hosts = tuple(args.hosts)
    if args.dry_run:
        events = (
            random_events(
                5, hosts, datetime.now(timezone.utc) - timedelta(minutes=5),
                datetime.now(timezone.utc), run_id, 0, random.Random(args.seed),
            )
            if args.live_minutes is not None
            else generate_events(
                args.count, args.hours, hosts, datetime.now(timezone.utc),
                run_id, 42 if args.seed is None else args.seed,
            )[:5]
        )
        print(json.dumps(events, indent=2))
        if args.live_minutes is None:
            print(f"Generated {args.count} synthetic events across {args.hours:g} hours")
        return 0

    secret = os.environ.get("LOG_INGEST_SHARED_SECRET")
    if not secret:
        parser.error("LOG_INGEST_SHARED_SECRET must be set in the environment")
    url = args.api_url.rstrip("/") + "/logs/ingest"
    try:
        if args.live_minutes is not None:
            run_live(
                args.live_minutes * 60, hosts, run_id,
                lambda batch: post_events(batch, url, args.route_host, secret),
                rng=random.Random(args.seed),
            )
        else:
            events = generate_events(
                args.count, args.hours, hosts, datetime.now(timezone.utc),
                run_id, 42 if args.seed is None else args.seed,
            )
            created = post_events(events, url, args.route_host, secret)
            print(
                f"Accepted {len(events)} synthetic events "
                f"({created} new, {len(events) - created} existing; run ID: {run_id})"
            )
    except (ValueError, RuntimeError) as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
