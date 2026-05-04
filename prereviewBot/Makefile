COMPOSE ?= docker compose

.PHONY: help build up down restart logs lint test shell

help:
	@echo "Targets:"
	@echo "  build    Build the Docker image"
	@echo "  up       Start the bot (detached)"
	@echo "  down     Stop the bot"
	@echo "  restart  Rebuild and restart"
	@echo "  logs     Tail bot logs"
	@echo "  lint     Run ruff against src/"
	@echo "  test     Run unit tests (pytest)"
	@echo "  shell    Open a shell in the running container"

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart: down build up

logs:
	$(COMPOSE) logs -f --tail=200

lint:
	$(COMPOSE) run --rm --no-deps --entrypoint "" bot ruff check /app/src

test:
	$(COMPOSE) run --rm --no-deps --entrypoint "" bot \
		sh -c "PYTHONPATH=/app/src pytest /app/src/tests || ([ \$$? -eq 5 ] && echo 'no tests collected (skipping)')"

shell:
	$(COMPOSE) exec bot bash
