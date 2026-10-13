from locust import HttpUser, between, task


class ChaosGateUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def work(self) -> None:
        self.client.get("/work", name="/work")

