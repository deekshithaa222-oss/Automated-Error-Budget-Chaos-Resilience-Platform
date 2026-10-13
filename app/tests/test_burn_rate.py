import pytest

from chaosgate.burn_rate import build_samples, calculate_burn_rate, decide


def test_calculate_burn_rate_for_999_slo() -> None:
    error_ratio, burn = calculate_burn_rate(bad_rate=1, total_rate=100, slo_target=0.999)
    assert error_ratio == pytest.approx(0.01)
    assert burn == pytest.approx(10.0)


def test_calculate_burn_rate_clamps_prometheus_extrapolation_noise() -> None:
    error_ratio, burn = calculate_burn_rate(bad_rate=101, total_rate=100, slo_target=0.999)
    assert error_ratio == pytest.approx(1.0)
    assert burn == pytest.approx(1000.0)


def test_page_decision_requires_short_and_long_windows() -> None:
    samples = build_samples(
        {
            "page-short": (100, 2),
            "page-long": (100, 2),
            "ticket-short": (100, 0),
            "ticket-long": (100, 0),
        },
        slo_target=0.999,
    )

    decision = decide(samples)

    assert decision.breached is True
    assert decision.severity == "page"
    assert decision.max_burn_rate == pytest.approx(20.0)


def test_single_short_spike_does_not_trip_multi_window_gate() -> None:
    samples = build_samples(
        {
            "page-short": (100, 2),
            "page-long": (100, 0),
            "ticket-short": (100, 0),
            "ticket-long": (100, 0),
        },
        slo_target=0.999,
    )

    decision = decide(samples)

    assert decision.breached is False
    assert decision.severity == "ok"

