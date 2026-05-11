# Makefile para TMJRApp
# Uso: make <target>   (sin args muestra la ayuda)

SHELL := /usr/bin/env bash

VENV    ?= .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
PYTEST  := $(VENV)/bin/pytest
ALEMBIC := $(VENV)/bin/alembic

.DEFAULT_GOAL := help

.PHONY: help venv install build test test-cov \
        run-dev run-dev-api run-dev-bot migrate \
        compose-up compose-down compose-logs \
        cert webhook-set webhook-info webhook-delete \
        deploy-tar clean

help: ## Lista los targets disponibles
	@awk 'BEGIN{FS=":.*##"; printf "Targets:\n"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- entorno ---------------------------------------------------------------

venv: ## Crea .venv si no existe
	@test -d $(VENV) || python3 -m venv $(VENV)

install: venv ## Instala requirements-dev.txt en .venv
	$(PIP) install -U pip
	$(PIP) install -r requirements-dev.txt

# --- build / test ----------------------------------------------------------

build: ## Construye la imagen Docker tmjrapp:<VERSION> y :latest
	bash scripts/build.sh

test: ## Ejecuta la suite pytest (smoke/e2e ya excluidos en pyproject)
	$(PYTEST)

test-cov: ## pytest con cobertura sobre el paquete tmjr
	$(PYTEST) --cov=tmjr --cov-report=term-missing

# --- desarrollo local ------------------------------------------------------

run-dev: ## Postgres + API (uvicorn --reload) + bot polling
	bash scripts/run-dev.sh full

run-dev-api: ## Postgres + API solamente (sin bot)
	bash scripts/run-dev.sh api

run-dev-bot: ## Postgres + bot polling solamente (sin API)
	bash scripts/run-dev.sh bot

migrate: ## Aplica migraciones de Alembic (alembic upgrade head)
	$(ALEMBIC) upgrade head

# --- compose (Postgres + app + nginx, perfil public) ----------------------

compose-up: ## docker compose up -d (perfil public)
	docker compose --profile public up -d

compose-down: ## docker compose down
	docker compose down

compose-logs: ## docker compose logs -f
	docker compose logs -f

# --- TLS / webhook Telegram ------------------------------------------------

cert: ## Genera cert self-signed en certs/
	bash scripts/generate-cert.sh

webhook-set: ## Registra el webhook en Telegram con el cert
	bash scripts/set-webhook.sh

webhook-info: ## getWebhookInfo: estado actual del webhook
	bash scripts/set-webhook.sh --info

webhook-delete: ## deleteWebhook: elimina el webhook
	bash scripts/set-webhook.sh --delete

# --- deploy QNAP -----------------------------------------------------------

deploy-tar: ## Genera docker-compose-env.yaml + tarball para QNAP
	bash scripts/build-compose-env.sh

# --- limpieza --------------------------------------------------------------

clean: ## Borra cachés de pytest, __pycache__ y .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .coverage