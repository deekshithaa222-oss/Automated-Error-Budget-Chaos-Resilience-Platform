from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class Severity(StrEnum):
    OK = "ok"
    TICKET = "ticket"
    PAGE = "page"


@dataclass(frozen=True)
class BurnRateWindow:
    name: str
    range_selector: str
    threshold: float
    severity: Severity
    budget_consumed_percent: float


@dataclass(frozen=True)
class BurnRateSample:
    window: BurnRateWindow
    total_rate: float
    bad_rate: float
    error_ratio: float
    burn_rate: float

    @property
    def breached(self) -> bool:
        return self.burn_rate >= self.window.threshold


@dataclass(frozen=True)
class BurnRateDecision:
    severity: Severity
    breached: bool
    reason: str
    samples: tuple[BurnRateSample, ...]

    @property
    def max_burn_rate(self) -> float:
        return max((sample.burn_rate for sample in self.samples), default=0.0)


DEFAULT_WINDOWS: tuple[BurnRateWindow, ...] = (
    # Google SRE Workbook page-grade alert pair: 2% of a 30-day budget in 1 hour.
    BurnRateWindow("page-short", "5m", 14.4, Severity.PAGE, 2.0),
    BurnRateWindow("page-long", "1h", 14.4, Severity.PAGE, 2.0),
    # Google SRE Workbook ticket-grade alert pair: 5% of a 30-day budget in 6 hours.
    BurnRateWindow("ticket-short", "30m", 6.0, Severity.TICKET, 5.0),
    BurnRateWindow("ticket-long", "6h", 6.0, Severity.TICKET, 5.0),
)


def error_budget(slo_target: float) -> float:
    if not 0 < slo_target < 1:
        raise ValueError("SLO target must be between 0 and 1, for example 0.999")
    return 1.0 - slo_target


def calculate_burn_rate(bad_rate: float, total_rate: float, slo_target: float) -> tuple[float, float]:
    if total_rate <= 0:
        return 0.0, 0.0
    ratio = min(max(bad_rate, 0.0) / total_rate, 1.0)
    return ratio, ratio / error_budget(slo_target)


def build_samples(
    raw_rates: dict[str, tuple[float, float]],
    slo_target: float,
    windows: Iterable[BurnRateWindow] = DEFAULT_WINDOWS,
) -> tuple[BurnRateSample, ...]:
    samples: list[BurnRateSample] = []
    for window in windows:
        total_rate, bad_rate = raw_rates.get(window.name, (0.0, 0.0))
        error_ratio, burn = calculate_burn_rate(bad_rate, total_rate, slo_target)
        samples.append(
            BurnRateSample(
                window=window,
                total_rate=total_rate,
                bad_rate=bad_rate,
                error_ratio=error_ratio,
                burn_rate=burn,
            )
        )
    return tuple(samples)


def decide(samples: Iterable[BurnRateSample]) -> BurnRateDecision:
    sample_tuple = tuple(samples)
    page_breaches = [s for s in sample_tuple if s.window.severity == Severity.PAGE and s.breached]
    ticket_breaches = [s for s in sample_tuple if s.window.severity == Severity.TICKET and s.breached]

    page_names = {s.window.name for s in page_breaches}
    ticket_names = {s.window.name for s in ticket_breaches}

    if {"page-short", "page-long"}.issubset(page_names):
        return BurnRateDecision(
            severity=Severity.PAGE,
            breached=True,
            reason="page-grade multi-window burn-rate breach: 5m and 1h windows exceeded 14.4x",
            samples=sample_tuple,
        )

    if {"ticket-short", "ticket-long"}.issubset(ticket_names):
        return BurnRateDecision(
            severity=Severity.TICKET,
            breached=True,
            reason="ticket-grade multi-window burn-rate breach: 30m and 6h windows exceeded 6x",
            samples=sample_tuple,
        )

    return BurnRateDecision(
        severity=Severity.OK,
        breached=False,
        reason="all burn-rate windows are within budget",
        samples=sample_tuple,
    )

