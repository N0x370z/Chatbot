.PHONY: dev worker test test-live lint check build up logs down

dev:
	LOG_LEVEL=DEBUG python main.py

worker:
	python main_worker.py

# Tests rápidos, sin red (lo que corre CI en cada push).
test:
	pytest -q

# Busca y descarga un libro real en cada fuente. Tarda unos minutos.
test-live:
	pytest -m live -v -rxX

lint:
	ruff check .

check: lint test

build:
	docker compose build

up:
	docker compose up --build -d

logs:
	docker compose logs -f

down:
	docker compose down
