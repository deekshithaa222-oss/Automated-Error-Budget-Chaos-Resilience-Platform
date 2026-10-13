from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from chaosgate.burn_rate import BurnRateDecision
from chaosgate.prometheus import burn_rate_queries


def write_postmortem(
    directory: Path,
    decision: BurnRateDecision,
    action: str,
    service_name: str,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    observed_at = datetime.now(UTC)
    filename = f"{observed_at.strftime('%Y%m%dT%H%M%SZ')}-{service_name}-burn-rate-breach.json"
    path = directory / filename

    query_by_window = {item.window.name: item for item in burn_rate_queries()}
    payload = {
        "schema_version": "chaosgate.postmortem.v1",
        "observed_at": observed_at.isoformat(),
        "service": service_name,
        "severity": decision.severity,
        "reason": decision.reason,
        "automated_action": action,
        "samples": [
            {
                "window": sample.window.name,
                "range": sample.window.range_selector,
                "threshold": sample.window.threshold,
                "budget_consumed_percent": sample.window.budget_consumed_percent,
                "total_rate": sample.total_rate,
                "bad_rate": sample.bad_rate,
                "error_ratio": sample.error_ratio,
                "burn_rate": sample.burn_rate,
                "breached": sample.breached,
                "promql": {
                    "total": query_by_window[sample.window.name].total_query,
                    "bad": query_by_window[sample.window.name].bad_query,
                },
            }
            for sample in decision.samples
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

