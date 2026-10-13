from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ControllerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    prometheus_url: str = Field("http://localhost:9090", alias="PROMETHEUS_URL")
    proxy_admin_url: str = Field("http://localhost:8080", alias="PROXY_ADMIN_URL")
    proxy_admin_token: str = Field("chaosgate-local", alias="PROXY_ADMIN_TOKEN")
    service_name: str = Field("chaosgate-proxy", alias="SERVICE_NAME")
    slo_target: float = Field(0.999, alias="SLO_TARGET")
    evaluation_interval_seconds: int = Field(15, alias="EVALUATION_INTERVAL_SECONDS")
    postmortem_dir: Path = Field(Path("postmortems"), alias="POSTMORTEM_DIR")
    enable_kubernetes_rollback: bool = Field(False, alias="ENABLE_KUBERNETES_ROLLBACK")
    kubernetes_namespace: str = Field("default", alias="KUBERNETES_NAMESPACE")
    kubernetes_canary_deployment: str = Field("chaosgate-canary", alias="KUBERNETES_CANARY_DEPLOYMENT")


@lru_cache
def controller_settings() -> ControllerSettings:
    return ControllerSettings()

