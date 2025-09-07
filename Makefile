# =========================
# Project Makefile (Dev + i18n, robust, lossless)
# =========================

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.PHONY: help run-dev up-dev logs restart-bot down rebuild build-bot build-ml-service clean \
        i18n-tools-check i18n-extract i18n-init i18n-update i18n-apply-review i18n-normalize \
        i18n-dedupe i18n-review i18n-clean-obsolete i18n-check i18n-compile \
        i18n-all i18n-set-translator \
        rebuild-cloud up-cloud down-cloud logs-cloud \
        set-bot-info-cloud setup-cloud

# -------------------------
# Dev workflow
# -------------------------
FULL_COMPOSE_ARGS = --env-file .env -f docker-compose.yml


# Start all services in background (alias to up-dev).
run-dev: up-dev

# Start services (detached).
up-dev:
	@echo "Starting development environment (docker compose up -d)…"
	@docker compose $(FULL_COMPOSE_ARGS) up -d

# Follow logs (set SERVICE=<name> to focus a service, default: all).
logs:
	@echo "Tailing logs (Ctrl+C to stop)…"
	@if [ -n "$${SERVICE-}" ]; then docker compose logs -f "$${SERVICE}"; else docker compose logs -f; fi

# Recreate only the bot service without deps.
restart-bot:
	@echo "Recreating the bot service…"
	@docker compose $(FULL_COMPOSE_ARGS) up -d --force-recreate --no-deps aiogram-bot

# Stop and remove containers, networks (keep volumes).
down:
	@echo "Stopping services…"
	@docker compose $(FULL_COMPOSE_ARGS) down

# Rebuild ONLY the bot image from scratch and restart it.
rebuild-bot:
	@echo "Rebuilding aiogram-bot (no cache) and restarting…"
	@docker compose $(FULL_COMPOSE_ARGS) build --no-cache aiogram-bot
	@docker compose $(FULL_COMPOSE_ARGS) up -d --force-recreate --no-deps aiogram-bot

# Build both ML service and Bot from scratch, then restart everything.
rebuild:
	@echo "--- Starting full project rebuild ---"
	@echo "[1/4] Stopping and cleaning up old environment..."
	@docker compose $(FULL_COMPOSE_ARGS) down --remove-orphans
	@echo "[2/4] Building local ML service..."
	@$(MAKE) build-ml-service
	@echo "[3/4] Rebuilding aiogram-bot image (no cache)..."
	@docker compose $(FULL_COMPOSE_ARGS) build --no-cache aiogram-bot
	@echo "[4/4] Starting all services..."
	@docker compose $(FULL_COMPOSE_ARGS) up -d
	@echo "--- Full rebuild complete! ---"

# Build bot image (using cache).
build-bot:
	@echo "Building aiogram-bot image…"
	@docker compose $(FULL_COMPOSE_ARGS) build aiogram-bot

# Build ML service artifacts (adjust if you have a different entrypoint).
build-ml-service:
	@echo "Running Python build script for ML service…"
	@poetry run python build.py

# Remove Python caches and compiled locales.
clean:
	@echo "Cleaning caches and compiled artifacts…"
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find aiogram_bot_template/locales -type f -name "*.mo" -delete || true

# -------------------------
# i18n configuration
# -------------------------

# Эта директива решает проблему с многострочными скриптами, делая их надежными
.ONESHELL:

I18N_DIR     := aiogram_bot_template/locales
I18N_DOMAIN  := messages
POT          := $(I18N_DIR)/$(I18N_DOMAIN).pot
BABEL_CFG    := babel.cfg
LOCALES      := en es ru
PO_FILES     := $(foreach L,$(LOCALES),$(I18N_DIR)/$(L)/LC_MESSAGES/$(I18N_DOMAIN).po)

# Определяем, как запускать pybabel (предпочитаем через poetry)
PYBABEL := $(shell command -v poetry >/dev/null 2>&1 && echo "poetry run pybabel" || echo "pybabel")

# Главная команда для полного цикла обновления переводов
# Обратите внимание на порядок: update -> apply-review -> review
i18n-all: i18n-extract i18n-update i18n-apply-review i18n-review i18n-check i18n-compile
	@echo "✅ i18n-all complete."

# 1. Извлекаем все строки из кода в .pot шаблон
i18n-extract:
	@echo "--- 1. Extracting strings to $(POT)..."
	$(PYBABEL) extract -F $(BABEL_CFG) -o $(POT) .

# 2. Обновляем .po файлы каждого языка на основе .pot шаблона
i18n-update:
	@echo "--- 2. Updating PO files from $(POT)..."
	for L in $(LOCALES)
	do
		PO_FILE="$(I18N_DIR)/$$L/LC_MESSAGES/$(I18N_DOMAIN).po"
		if [ ! -f "$$PO_FILE" ]; then
			echo "   - Initializing $$L..."
			mkdir -p "$$(dirname "$$PO_FILE")"
			$(PYBABEL) init -i $(POT) -d $(I18N_DIR) -D $(I18N_DOMAIN) -l $$L
		else
			echo "   - Updating $$L..."
			$(PYBABEL) update -i $(POT) -d $(I18N_DIR) -D $(I18N_DOMAIN) -l $$L --previous
		fi
	done

# 3. ПРИМЕНЯЕМ переводы из .review.po в основные .po файлы
i18n-apply-review:
	@echo "--- 3. Applying translations from review files..."
	for PO in $(PO_FILES)
	do
		REVIEW_FILE="$$(dirname "$$PO")/$(I18N_DOMAIN).review.po"
		# Проверяем, существует ли review файл и не пустой ли он
		if [ -f "$$REVIEW_FILE" ] && [ -s "$$REVIEW_FILE" ]; then
			# Используем msgcat, чтобы объединить файлы. --use-first говорит,
			# что если строка есть в обоих файлах, нужно брать версию из первого (из review.po)
			TEMP_MERGED="$${PO}.merged"
			msgcat --use-first "$$REVIEW_FILE" "$$PO" -o "$$TEMP_MERGED"
			
			# Проверяем, что в объединенном файле есть переводы, которых не было в оригинале
			# Это предотвращает перезапись файла, если в review.po не было ничего полезного
			if ! diff -q "$$PO" "$$TEMP_MERGED" >/dev/null; then
				echo "   - Merging translations into $$PO"
				mv "$$TEMP_MERGED" "$$PO"
			else
				echo "   - No new translations to apply for $$PO"
				rm -f "$$TEMP_MERGED"
			fi
		else
			echo "   - Skipping $$PO (review file is missing or empty)"
		fi
	done

# 4. Создаем .review.po файлы, которые содержат ТОЛЬКО непереведенные или нечеткие строки
i18n-review:
	@echo "--- 4. Building review files (untranslated or fuzzy)..."
	for PO in $(PO_FILES)
	do
		REVIEW_FILE="$$(dirname "$$PO")/$(I18N_DOMAIN).review.po"
		echo "   - Generating review file for $$PO"
		# Эта команда извлекает нужные строки. || true защищает от ошибок.
		msgattrib --untranslated --only-fuzzy --no-obsolete -o "$$REVIEW_FILE" "$$PO" || true
		
		COUNT=$$(expr $$(grep -c '^msgid ' "$$REVIEW_FILE" 2>/dev/null || echo 0) - 1)
		if [ $$COUNT -gt 0 ]; then
			echo "     => Review file updated: $$REVIEW_FILE ($$COUNT entries)"
		else
			echo "     => No new entries for review. Review file is empty."
		fi
	done

# 5. Проверяем корректность .po файлов
i18n-check:
	@echo "--- 5. Checking PO files for errors..."
	for PO in $(PO_FILES)
	do
		echo "   - Checking $$PO..."
		msgfmt --check-format --check-header -o /dev/null "$$PO"
	done

# 6. Компилируем .po файлы в бинарные .mo, которые использует бот
i18n-compile:
	@echo "--- 6. Compiling MO files..."
	$(PYBABEL) compile -d $(I18N_DIR) -D $(I18N_DOMAIN) --statistics

# Вспомогательная команда для установки имени переводчика
i18n-set-translator:
	@if [ -z "$${LAST_TRANSLATOR-}" ]; then echo "ERROR: set LAST_TRANSLATOR env var (e.g., 'John Doe <j.doe@example.com>')"; exit 1; fi
	@echo "Setting Last-Translator header to '$${LAST_TRANSLATOR}'..."
	for PO in $(PO_FILES)
	do
		echo " - $$PO"
		sed -i -e "s/^\"Last-Translator: .*\"/\"Last-Translator: $${LAST_TRANSLATOR}\"/" "$$PO"
	done
	
# ==============================================================================
# === NEW SECTION: BOT INFO MANAGEMENT =========================================
# ==============================================================================

# Устанавливает команды/описание для CLOUD окружения
set-bot-info-cloud:
	@echo "ℹ️ Setting bot info using .env.cloud..."
	@ENV_FILE_PATH=.env.cloud poetry run python -m scripts.set_bot_info


# ==============================================================================
# === CLOUD-ONLY DEPLOYMENT ====================================================
# ==============================================================================

CLOUD_COMPOSE_ARGS = --env-file .env.cloud -f docker-compose.cloud.yml

# Полная настройка: установка информации о боте + сборка и запуск
setup-cloud: set-bot-info-cloud rebuild-cloud
	@echo "✅ Cloud environment is set up and running."

# Собрать и запустить "облачную" версию с нуля
rebuild-cloud:
	@echo "--- Building and running CLOUD-ONLY version ---"
	@docker compose $(CLOUD_COMPOSE_ARGS) down --remove-orphans
	@docker compose $(CLOUD_COMPOSE_ARGS) build --no-cache --build-arg INSTALL_MODE=cloud
	@docker compose $(CLOUD_COMPOSE_ARGS) up -d --remove-orphans

# Просто запустить "облачную" версию
up-cloud:
	@echo "--- Starting CLOUD-ONLY version ---"
	@docker compose $(CLOUD_COMPOSE_ARGS) up -d

# Остановить "облачную" версию
down-cloud:
	@echo "--- Stopping CLOUD-ONLY version ---"
	@docker compose $(CLOUD_COMPOSE_ARGS) down

# Посмотреть логи "облачной" версии
logs-cloud:
	@echo "--- Tailing logs for CLOUD-ONLY version ---"
	@docker compose $(CLOUD_COMPOSE_ARGS) logs -f


# -------------------------
# Help
# -------------------------

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "High-level targets:"
	@echo "  setup-cloud      - First-time setup: sets bot info, then rebuilds and runs the cloud environment."
	@echo "  rebuild-cloud    - Rebuilds and restarts the cloud environment without touching bot info."
	@echo ""
	@echo "Bot Info Management:"
	@echo "  set-bot-info-cloud - Sets bot commands/description using .env.cloud (run once)."
	@echo ""
	@echo "Dev targets (Local ML):"
	@echo "  run-dev        - Start local dev services (alias to up-dev)."
	@echo "  up-dev         - Start local dev services in background."
	@echo "  logs           - Tail logs (SERVICE=<name> to filter)."
	@echo "  restart-bot    - Recreate only aiogram-bot service."
	@echo "  down           - Stop local dev services."
	@echo "  rebuild        - Full rebuild of local ML service and bot."
	@echo "  build-ml-service - Run ML service build script."
	@echo "  clean          - Remove caches and compiled locales."
	@echo ""
	@echo "Cloud-only targets:"
	@echo "  up-cloud         - Start cloud services."
	@echo "  down-cloud       - Stop cloud services."
	@echo "  logs-cloud       - Tail cloud logs."
	@echo ""
	@echo "i18n targets:"
	@echo "  i18n-all       - Run the full i18n pipeline."
	@echo "  ... (see Makefile for more granular i18n commands)"

.DEFAULT_GOAL := help