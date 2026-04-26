.PHONY: dev worker test build up logs down

dev:
	LOG_LEVEL=DEBUG python main.py

worker:
	python main_worker.py

test:
	pytest tests/ -v

build:
	docker compose build

up:
	docker compose up --build -d

logs:
	docker compose logs -f

down:
	docker compose down
