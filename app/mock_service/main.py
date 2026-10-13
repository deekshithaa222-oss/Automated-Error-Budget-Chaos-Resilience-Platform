from __future__ import annotations

import asyncio
import os
import random
import time

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

SHARD_NAME = os.getenv("SHARD_NAME", "local")
BASE_DELAY_MS = float(os.getenv("BASE_DELAY_MS", "25"))
JITTER_MS = float(os.getenv("JITTER_MS", "10"))
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.001"))

REQUESTS = Counter(
    "mock_service_requests_total",
    "Requests received by a mock shard.",
    ("shard", "status_code"),
)
LATENCY = Histogram(
    "mock_service_request_duration_seconds",
    "Mock service handler latency.",
    ("shard",),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1, 2, 5),
)
IN_FLIGHT = Gauge("mock_service_in_flight_requests", "In-flight requests by shard.", ("shard",))

app = FastAPI(title=f"ChaosGate Mock Service: {SHARD_NAME}", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "shard": SHARD_NAME}


@app.get("/work")
async def work() -> Response:
    start = time.perf_counter()
    IN_FLIGHT.labels(SHARD_NAME).inc()
    status_code = 200
    try:
        delay = BASE_DELAY_MS + random.uniform(0, JITTER_MS)
        await asyncio.sleep(delay / 1000)
        if random.random() < ERROR_RATE:
            status_code = 500
            return Response(
                content=f"{SHARD_NAME} injected application error\n",
                status_code=status_code,
                media_type="text/plain",
            )
        return Response(
            content=f"{SHARD_NAME} response ok\n",
            status_code=status_code,
            media_type="text/plain",
        )
    finally:
        elapsed = time.perf_counter() - start
        REQUESTS.labels(SHARD_NAME, str(status_code)).inc()
        LATENCY.labels(SHARD_NAME).observe(elapsed)
        IN_FLIGHT.labels(SHARD_NAME).dec()


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

