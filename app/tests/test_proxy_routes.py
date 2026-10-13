from fastapi.testclient import TestClient

from proxy.main import app


def test_metrics_route_is_not_forwarded_to_upstream() -> None:
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert b"chaosgate_proxy_requests_total" in response.content

