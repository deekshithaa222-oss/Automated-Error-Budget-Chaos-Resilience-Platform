from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RollbackResult:
    action: str
    detail: str


class ProxyCircuitBreaker:
    def __init__(self, admin_url: str, token: str) -> None:
        self.admin_url = admin_url.rstrip("/")
        self.token = token

    async def close_canary(self) -> RollbackResult:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{self.admin_url}/admin/circuit",
                headers={"x-chaosgate-token": self.token},
                json={"canary_enabled": False, "canary_percent": 0},
            )
            response.raise_for_status()
            payload = response.json()
        return RollbackResult("proxy_circuit_closed", f"proxy state: {payload}")


class KubernetesRollback:
    def __init__(self, namespace: str, deployment: str) -> None:
        self.namespace = namespace
        self.deployment = deployment

    def scale_canary_to_zero(self) -> RollbackResult:
        try:
            from kubernetes import client, config
            from kubernetes.config.config_exception import ConfigException
        except Exception as exc:  # pragma: no cover - dependency import guard
            return RollbackResult("kubernetes_skipped", f"kubernetes client unavailable: {exc}")

        try:
            try:
                config.load_incluster_config()
            except ConfigException:
                config.load_kube_config()

            apps_v1 = client.AppsV1Api()
            patch = {"spec": {"replicas": 0}}
            apps_v1.patch_namespaced_deployment_scale(
                name=self.deployment,
                namespace=self.namespace,
                body=patch,
            )
            return RollbackResult(
                "kubernetes_canary_scaled_to_zero",
                f"deployment {self.namespace}/{self.deployment} replicas set to 0",
            )
        except Exception as exc:  # pragma: no cover - requires cluster
            LOGGER.exception("Kubernetes rollback failed")
            return RollbackResult("kubernetes_failed", str(exc))

