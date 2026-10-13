from __future__ import annotations

import asyncio
import logging
import signal

from chaosgate.burn_rate import build_samples, decide
from chaosgate.config import controller_settings
from chaosgate.postmortem import write_postmortem
from chaosgate.prometheus import PrometheusClient
from chaosgate.rollback import KubernetesRollback, ProxyCircuitBreaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
LOGGER = logging.getLogger("chaosgate.controller")


class BurnRateController:
    def __init__(self) -> None:
        self.settings = controller_settings()
        self.prometheus = PrometheusClient(self.settings.prometheus_url)
        self.proxy = ProxyCircuitBreaker(
            self.settings.proxy_admin_url,
            self.settings.proxy_admin_token,
        )
        self.kubernetes = KubernetesRollback(
            self.settings.kubernetes_namespace,
            self.settings.kubernetes_canary_deployment,
        )
        self._rollback_completed = False

    async def evaluate_once(self) -> None:
        raw_rates = await self.prometheus.fetch_window_rates()
        samples = build_samples(raw_rates, self.settings.slo_target)
        decision = decide(samples)

        LOGGER.info(
            "burn-rate decision=%s max=%.2fx reason=%s",
            decision.severity,
            decision.max_burn_rate,
            decision.reason,
        )

        if not decision.breached:
            return

        if self._rollback_completed:
            LOGGER.info("breach still active; rollback has already been executed")
            return

        proxy_result = await self.proxy.close_canary()
        action = proxy_result.action
        details = [proxy_result.detail]

        if self.settings.enable_kubernetes_rollback:
            k8s_result = self.kubernetes.scale_canary_to_zero()
            action = f"{action},{k8s_result.action}"
            details.append(k8s_result.detail)

        artifact = write_postmortem(
            self.settings.postmortem_dir,
            decision,
            action=f"{action}: {'; '.join(details)}",
            service_name=self.settings.service_name,
        )
        self._rollback_completed = True
        LOGGER.warning("rollback executed; postmortem artifact written to %s", artifact)

    async def run_forever(self) -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        while not stop.is_set():
            try:
                await self.evaluate_once()
            except Exception:
                LOGGER.exception("controller evaluation failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.settings.evaluation_interval_seconds)
            except asyncio.TimeoutError:
                continue


async def main() -> None:
    await BurnRateController().run_forever()


if __name__ == "__main__":
    asyncio.run(main())

