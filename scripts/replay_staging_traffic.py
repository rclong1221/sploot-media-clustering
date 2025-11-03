#!/usr/bin/env python3
"""Replay media clustering jobs against a target environment.

Example:
    python scripts/replay_staging_traffic.py \
        --base-url https://media-clustering.staging.sploot.internal \
        --token $INTERNAL_TOKEN \
        --payloads docs/examples/staging-jobs.json \
        --duration 3600
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

DEFAULT_ENDPOINT = "/internal/cluster-jobs"
DEFAULT_TIMEOUT = 10


def load_payloads(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    raise ValueError(f"Expected a list of job envelopes in {path}")


def build_request(base_url: str, token: str, payload: dict) -> urllib.request.Request:
    url = f"{base_url.rstrip('/')}{DEFAULT_ENDPOINT}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Internal-Token", token)
    return request


def replay_jobs(
    base_url: str,
    token: str,
    payloads: Iterable[dict],
    pause_seconds: float,
    duration_seconds: int,
    jitter_seconds: float,
) -> None:
    start = time.monotonic()
    count = 0
    payload_cycle = list(payloads)
    if not payload_cycle:
        raise ValueError("At least one payload is required")

    while time.monotonic() - start < duration_seconds:
        payload = payload_cycle[count % len(payload_cycle)]
        request = build_request(base_url, token, payload)
        try:
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                if response.status != 202:
                    print(f"non-202 response: {response.status}", file=sys.stderr)
        except urllib.error.URLError as err:
            print(f"request failed: {err}", file=sys.stderr)
        count += 1

        sleep_time = pause_seconds + random.uniform(-jitter_seconds, jitter_seconds)
        time.sleep(max(0.0, sleep_time))

    print(f"Completed {count} job submissions in {duration_seconds} seconds")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay clustering jobs against an environment")
    parser.add_argument("--base-url", required=True, help="Media clustering base URL (e.g. https://host:9007)")
    parser.add_argument("--token", required=True, help="Internal auth token")
    parser.add_argument("--payloads", type=Path, required=True, help="Path to JSON file containing job payloads")
    parser.add_argument("--duration", type=int, default=3600, help="Total duration in seconds (default: 3600)")
    parser.add_argument("--pause", type=float, default=1.5, help="Average pause between jobs in seconds (default: 1.5)")
    parser.add_argument(
        "--jitter",
        type=float,
        default=0.5,
        help="Random jitter (+/- seconds) added to the pause to avoid burst patterns (default: 0.5)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    payloads = load_payloads(args.payloads)

    try:
        replay_jobs(
            base_url=args.base_url,
            token=args.token,
            payloads=payloads,
            pause_seconds=args.pause,
            duration_seconds=args.duration,
            jitter_seconds=args.jitter,
        )
    except Exception as err:  # noqa: BLE001 - CLI should bubble up failures
        print(f"Error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
