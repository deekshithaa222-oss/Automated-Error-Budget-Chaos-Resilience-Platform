.PHONY: test up down load chaos-delay chaos-loss chaos-partition chaos-clear logs

test:
	pytest -q

up:
	docker compose up --build -d

down:
	docker compose down --remove-orphans

load:
	docker compose --profile load up --build locust

chaos-delay:
	python scripts/chaos_injector.py delay --container $$(docker compose ps -q canary) --delay-ms 250 --jitter-ms 75

chaos-loss:
	python scripts/chaos_injector.py loss --container $$(docker compose ps -q canary) --loss-percent 5

chaos-partition:
	python scripts/chaos_injector.py partition --container $$(docker compose ps -q canary)

chaos-clear:
	python scripts/chaos_injector.py clear --container $$(docker compose ps -q canary)

logs:
	docker compose logs -f proxy controller

