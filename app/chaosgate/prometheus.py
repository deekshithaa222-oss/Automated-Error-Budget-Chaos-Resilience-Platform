from __future__ import annotations

from dataclasses import dataclass

import httpx

from chaosgate.burn_rate import DEFAULT_WINDOWS, BurnRateWindow


@dataclass(frozen=True)
class PrometheusQuery:
    window: BurnRateWindow
    total_query: str
    bad_query: str


def rate_query(metric: str, window: str, route: str = "canary", extra_matchers: str = "") -> str:
    labels = [f'route="{route}"']
    if extra_matchers:
        labels.append(extra_matchers)
    matcher = ",".join(labels)
    return f'sum(rate({metric}{{{matcher}}}[{window}]))'


def burn_rate_queries(windows: tuple[BurnRateWindow, ...] = DEFAULT_WINDOWS) -> tuple[PrometheusQuery, ...]:
    return tuple(
        PrometheusQuery(
            window=window,
            total_query=rate_query("chaosgate_proxy_sli_events_total", window.range_selector),
            bad_query=rate_query(
                "chaosgate_proxy_sli_events_total",
                window.range_selector,
                extra_matchers='outcome="bad"',
            ),
        )
        for window in windows
    )


class PrometheusClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def instant_query(self, query: str) -> float:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}/api/v1/query", params={"query": query})
            response.raise_for_status()
            payload = response.json()

        if payload.get("status") != "success":
            raise RuntimeError(f"Prometheus query failed: {payload}")

        result = payload.get("data", {}).get("result", [])
        if not result:
            return 0.0
        value = result[0].get("value", [None, "0"])[1]
        return float(value)

    async def fetch_window_rates(
        self,
        windows: tuple[BurnRateWindow, ...] = DEFAULT_WINDOWS,
    ) -> dict[str, tuple[float, float]]:
        rates: dict[str, tuple[float, float]] = {}
        for query in burn_rate_queries(windows):
            total_rate = await self.instant_query(query.total_query)
            bad_rate = await self.instant_query(query.bad_query)
            rates[query.window.name] = (total_rate, bad_rate)
        return rates

