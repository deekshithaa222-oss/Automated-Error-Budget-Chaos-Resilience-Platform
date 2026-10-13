from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field


REQUESTS = Counter(
    "chaosgate_proxy_requests_total",
    "HTTP requests routed through ChaosGate.",
    ("route", "method", "status_code"),
)
SLI_EVENTS = Counter(
    "chaosgate_proxy_sli_events_total",
    "Good and bad SLI events. Bad means 5xx or latency over the configured SLO.",
    ("route", "outcome"),
)
LATENCY = Histogram(
    "chaosgate_proxy_request_duration_seconds",
    "End-to-end proxy latency.",
    ("route",),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 2, 5),
)


@dataclass
class RoutingState:
    stable_url: str
    canary_url: str
    canary_percent: float
    canary_enabled: bool
    latency_slo_ms: float
    admin_token: str


class CircuitUpdate(BaseModel):
    canary_enabled: bool
    canary_percent: float = Field(ge=0, le=100)


def load_state() -> RoutingState:
    return RoutingState(
        stable_url=os.getenv("STABLE_URL", "http://localhost:8001").rstrip("/"),
        canary_url=os.getenv("CANARY_URL", "http://localhost:8002").rstrip("/"),
        canary_percent=float(os.getenv("CANARY_PERCENT", "5")),
        canary_enabled=os.getenv("CANARY_ENABLED", "true").lower() == "true",
        latency_slo_ms=float(os.getenv("LATENCY_SLO_MS", "300")),
        admin_token=os.getenv("PROXY_ADMIN_TOKEN", "chaosgate-local"),
    )


app = FastAPI(title="ChaosGate Admission Proxy", version="0.1.0")
state = load_state()


def choose_route() -> tuple[str, str]:
    if state.canary_enabled and random.uniform(0, 100) < state.canary_percent:
        return "canary", state.canary_url
    return "stable", state.stable_url


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/admin/state")
async def admin_state(x_chaosgate_token: str = Header(default="")) -> dict[str, object]:
    require_admin(x_chaosgate_token)
    return {
        "canary_enabled": state.canary_enabled,
        "canary_percent": state.canary_percent,
        "latency_slo_ms": state.latency_slo_ms,
    }


@app.post("/admin/circuit")
async def update_circuit(
    update: CircuitUpdate,
    x_chaosgate_token: str = Header(default=""),
) -> dict[str, object]:
    require_admin(x_chaosgate_token)
    state.canary_enabled = update.canary_enabled
    state.canary_percent = update.canary_percent
    return {
        "canary_enabled": state.canary_enabled,
        "canary_percent": state.canary_percent,
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    route, upstream = choose_route()
    target = f"{upstream}/{path}"
    start = time.perf_counter()
    status_code = 502
    content = b""
    headers: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            upstream_response = await client.request(
                request.method,
                target,
                params=request.query_params,
                content=await request.body(),
                headers={key: value for key, value in request.headers.items() if key.lower() != "host"},
            )
        status_code = upstream_response.status_code
        content = upstream_response.content
        headers = {
            key: value
            for key, value in upstream_response.headers.items()
            if key.lower() not in {"content-length", "transfer-encoding", "connection"}
        }
    except httpx.HTTPError as exc:
        content = f"upstream {route} unavailable: {exc}".encode()
        headers = {"content-type": "text/plain; charset=utf-8"}
    finally:
        elapsed = time.perf_counter() - start
        REQUESTS.labels(route=route, method=request.method, status_code=str(status_code)).inc()
        LATENCY.labels(route=route).observe(elapsed)
        bad = status_code >= 500 or elapsed * 1000 > state.latency_slo_ms
        SLI_EVENTS.labels(route=route, outcome="bad" if bad else "good").inc()

    headers["x-chaosgate-route"] = route
    return Response(content=content, status_code=status_code, headers=headers)


def require_admin(token: str) -> None:
    if token != state.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")

