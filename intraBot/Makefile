SHELL := /bin/bash

.PHONY: build up down logs lint test tunnel

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
	ruff check src || true

test:
	@echo "no tests configured"

# ngrok を <NGROK_DOMAIN> 環境変数で起動するヘルパー
# 例: NGROK_DOMAIN=intrabot-1234.ngrok-free.app make tunnel
tunnel:
	@if [ -z "$$NGROK_DOMAIN" ]; then \
		echo "NGROK_DOMAIN env var is required (e.g. intrabot-1234.ngrok-free.app)"; exit 1; \
	fi
	ngrok http --url=$$NGROK_DOMAIN 4242
