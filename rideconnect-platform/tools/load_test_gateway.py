"""Simple concurrent load generator for gateway ride requests.

Usage:
  python tools/load_test_gateway.py --url http://127.0.0.1:8100 --requests 200 --concurrency 25
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def _payload(i: int) -> dict:
    base_lat, base_lng = -1.9441, 30.0619
    dlat = random.uniform(-0.02, 0.02)
    dlng = random.uniform(-0.02, 0.02)
    return {
        "city_id": "kigali",
        "rider_id": f"bench-rider-{i}",
        "pickup_lat": base_lat + dlat,
        "pickup_lng": base_lng + dlng,
        "destination_lat": -1.9686,
        "destination_lng": 30.1395,
        "candidate_drivers": [
            {"driver_id": "d-1", "lat": -1.9450, "lng": 30.0600, "rating": 4.9, "available": True},
            {"driver_id": "d-2", "lat": -1.9520, "lng": 30.0880, "rating": 4.6, "available": True},
            {"driver_id": "d-3", "lat": -1.9300, "lng": 30.0500, "rating": 4.3, "available": True},
        ],
    }


def _one(url: str, i: int) -> tuple[bool, float, int]:
    started = time.perf_counter()
    req = urllib.request.Request(
        f"{url}/v1/rides/request",
        data=json.dumps(_payload(i)).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            latency_ms = (time.perf_counter() - started) * 1000.0
            return (200 <= resp.status < 300, latency_ms, resp.status)
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return (False, latency_ms, e.code)
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return (False, latency_ms, 0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8100")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=25)
    args = parser.parse_args()

    lock = threading.Lock()
    latencies = []
    ok = 0
    failed = 0

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(_one, args.url, i) for i in range(args.requests)]
        for fut in as_completed(futures):
            success, latency_ms, _ = fut.result()
            with lock:
                latencies.append(latency_ms)
                if success:
                    ok += 1
                else:
                    failed += 1

    elapsed = time.perf_counter() - started
    latencies.sort()

    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = int((p / 100.0) * (len(latencies) - 1))
        return latencies[idx]

    print(
        json.dumps(
            {
                "total_requests": args.requests,
                "concurrency": args.concurrency,
                "success": ok,
                "failed": failed,
                "duration_seconds": round(elapsed, 3),
                "rps": round(args.requests / max(elapsed, 1e-6), 2),
                "latency_ms": {
                    "p50": round(pct(50), 2),
                    "p95": round(pct(95), 2),
                    "p99": round(pct(99), 2),
                    "max": round(max(latencies) if latencies else 0.0, 2),
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
