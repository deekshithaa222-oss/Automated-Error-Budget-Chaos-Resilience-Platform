# ChaosGate

ChaosGate is an automated error-budget controller that protects a canary deployment with Google SRE style multi-window, multi-burn-rate alerting, active network fault injection, and automated rollback.

It runs locally with Docker Compose and includes:

- FastAPI admission proxy routing 95% stable / 5% canary traffic.
- Mock stable and canary production shards with Prometheus metrics.
- Burn-rate daemon implementing the Google SRE Workbook alert pairs: 5m + 1h at 14.4x and 30m + 6h at 6x.
- Kernel-level fault injection using Linux `tc`/`netem`.
- Automated circuit breaker that routes 100% of traffic back to stable.
- Structured postmortem artifacts containing the exact PromQL trace signatures.
- Grafana dashboard for the Four Golden Signals.
- Kubernetes manifests and RBAC for cluster rollback.

## Quick Start

```bash
docker compose up --build -d
docker compose --profile load up locust
```

Open:

- Proxy: <http://localhost:8080/work>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (`admin` / `admin`)
- Locust: <http://localhost:8089>

In Locust, start a run against `/work`. A few thousand requests per minute makes the canary metrics converge quickly.

## Inject Faults

Find the canary container name if your Compose project name differs:

```bash
docker compose ps canary
```

Then inject latency, packet loss, or a full partition:

```bash
python scripts/chaos_injector.py delay --container automated-error-budget-canary-1 --delay-ms 250 --jitter-ms 75
python scripts/chaos_injector.py loss --container automated-error-budget-canary-1 --loss-percent 5
python scripts/chaos_injector.py partition --container automated-error-budget-canary-1
python scripts/chaos_injector.py clear --container automated-error-budget-canary-1
```

The proxy counts a bad SLI event when a request returns `5xx` or exceeds `LATENCY_SLO_MS` milliseconds. Once both page windows breach, the controller closes the canary circuit:

```bash
curl -H 'x-chaosgate-token: chaosgate-local' http://localhost:8080/admin/state
```

Postmortems are written to `postmortems/*.json`.

## Run Tests

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Kubernetes

Build and load the image into a local cluster, then apply manifests:

```bash
docker build -t chaosgate:local .
kind load docker-image chaosgate:local
kubectl apply -f k8s/
```

The Kubernetes controller has RBAC permission only to patch `deployments/scale` in the `chaosgate` namespace. On breach it closes the proxy circuit and scales `chaosgate-canary` to zero replicas.

