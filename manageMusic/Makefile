SHELL := /bin/bash

.PHONY: build up down logs lint test web-shell bot-shell

build:
	docker compose build

up:
	docker compose up

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	pip install --quiet ruff
	ruff check bot/src web/src || true

test:
	@echo "no tests configured"

bot-shell:
	docker compose run --rm bot /bin/bash

web-shell:
	docker compose run --rm web /bin/bash
