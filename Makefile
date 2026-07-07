.PHONY: help dev test lint typecheck check build clean install
.PHONY: daemon-dev daemon-test daemon-lint daemon-typecheck daemon-check daemon-build daemon-install daemon-clean
.PHONY: webapp-dev webapp-test webapp-lint webapp-typecheck webapp-check webapp-build webapp-install webapp-clean
.PHONY: notebooks-install notebooks-run notebooks-clean

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Combined targets (daemon + webapp):"
	@echo "  dev         - Start both daemon and webapp in development mode"
	@echo "  test        - Run all tests"
	@echo "  lint        - Lint and format all code"
	@echo "  typecheck   - Type check all code"
	@echo "  check       - Full validation (lint + typecheck + test)"
	@echo "  build       - Build production artifacts (bundles webapp into daemon)"
	@echo "  clean       - Clean all build artifacts"
	@echo "  install     - Install all dependencies"
	@echo ""
	@echo "Daemon-specific targets:"
	@echo "  daemon-dev       - Run daemon in development mode"
	@echo "  daemon-test      - Run daemon tests"
	@echo "  daemon-lint      - Lint daemon code"
	@echo "  daemon-typecheck - Type check daemon code"
	@echo "  daemon-check     - Daemon validation (lint + typecheck + test)"
	@echo "  daemon-build     - Build webapp and bundle it into the daemon served path"
	@echo "  daemon-install   - Install daemon dependencies"
	@echo "  daemon-clean     - Clean daemon build artifacts"
	@echo ""
	@echo "Webapp-specific targets:"
	@echo "  webapp-dev       - Run webapp development server"
	@echo "  webapp-test      - Run webapp tests"
	@echo "  webapp-lint      - Lint webapp code"
	@echo "  webapp-typecheck - Type check webapp code"
	@echo "  webapp-check     - Webapp validation (lint + typecheck + test)"
	@echo "  webapp-build     - Build webapp for production"
	@echo "  webapp-install   - Install webapp dependencies"
	@echo "  webapp-clean     - Clean webapp build artifacts"
	@echo ""
	@echo "Notebooks-specific targets:"
	@echo "  notebooks-install - Install notebook dependencies"
	@echo "  notebooks-run     - Start Jupyter notebook server"
	@echo "  notebooks-clean   - Clean notebook build artifacts"

#
# Combined targets
#

dev:
	@echo "Starting daemon and webapp in development mode..."
	@echo "Starting daemon in background..."
	@uv run python -m lakehoused &
	@DAEMON_PID=$$!; \
	trap "echo 'Stopping daemon...'; kill $$DAEMON_PID 2>/dev/null || true" EXIT INT TERM; \
	echo "Starting webapp (daemon PID: $$DAEMON_PID)..."; \
	cd webapp && pnpm run dev

test: daemon-test webapp-test
	@echo "All tests passed"

lint: daemon-lint webapp-lint
	@echo "All code linted successfully"

typecheck: daemon-typecheck webapp-typecheck
	@echo "All code type-checked successfully"

check: lint typecheck test
	@echo "All validation checks passed"

build: webapp-build
	@echo "Frontend built to webapp/dist (served by the Castle 'lakehouse' static site)."
	@echo "The daemon is API-only. Deploy with: castle build lakehouse-web && castle apply"

clean: daemon-clean webapp-clean notebooks-clean
	@echo "All build artifacts cleaned"

install: daemon-install webapp-install notebooks-install
	@echo "All dependencies installed"

#
# Daemon-specific targets
#

daemon-dev:
	@echo "Starting daemon..."
	cd lakehoused && uv run python -m lakehoused

daemon-test:
	@echo "Running daemon tests..."
	cd lakehoused && uv run pytest

daemon-lint:
	@echo "Linting daemon code..."
	cd lakehoused && uv run ruff check --fix lakehoused
	@echo "Formatting daemon code..."
	cd lakehoused && uv run ruff format lakehoused

daemon-typecheck:
	@echo "Type checking daemon code..."
	cd lakehoused && uv run pyright lakehoused

daemon-check: daemon-lint daemon-typecheck daemon-test
	@echo "Daemon validation complete"

# Deprecated: the frontend is now served as a separate Castle static site
# (Caddy -> webapp/dist), not bundled into the daemon. The daemon serves the SPA
# only if lakehoused/lakehoused/webapp_dist exists (see lakehoused/main.py), so
# this target just removes any stale bundle to keep the daemon API-only.
# Use `make webapp-build` to produce webapp/dist for the static site.
daemon-build:
	@echo "Frontend is served separately; removing any bundled webapp_dist (daemon stays API-only)..."
	rm -rf lakehoused/lakehoused/webapp_dist

daemon-install:
	@echo "Installing daemon dependencies..."
	cd lakehoused && uv sync

daemon-clean:
	@echo "Cleaning daemon build artifacts..."
	rm -rf lakehoused/lakehoused/webapp_dist
	cd lakehoused && rm -rf __pycache__ .pytest_cache .ruff_cache .pyright_cache
	cd lakehoused && find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	cd lakehoused && find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

#
# Webapp-specific targets
#

webapp-dev:
	@echo "Starting webapp development server..."
	cd webapp && pnpm run dev --host

webapp-test:
	@echo "Checking for webapp tests..."
	@if [ -d "webapp/src/__tests__" ] || [ -d "webapp/tests" ] || [ -f "webapp/vitest.config.ts" ]; then \
		echo "Running webapp tests..."; \
		cd webapp && pnpm test; \
	else \
		echo "No webapp tests found - skipping"; \
	fi

webapp-lint:
	@echo "Linting webapp code..."
	cd webapp && pnpm run lint

webapp-typecheck:
	@echo "Type checking webapp code..."
	cd webapp && npx tsc --noEmit

webapp-check: webapp-lint webapp-typecheck webapp-test
	@echo "Webapp validation complete"

webapp-build:
	@echo "Building webapp for production..."
	cd webapp && pnpm run build

webapp-install:
	@echo "Installing webapp dependencies..."
	cd webapp && pnpm install

webapp-clean:
	@echo "Cleaning webapp build artifacts..."
	cd webapp && rm -rf dist build .next node_modules/.cache

#
# Notebooks-specific targets
#

notebooks-install:
	@echo "Installing notebook dependencies..."
	cd notebooks && uv sync

notebooks-run:
	@echo "Starting Jupyter notebook server..."
	@echo "Make sure to activate the notebook environment first:"
	@echo "  cd notebooks && source .venv/bin/activate && jupyter notebook"
	@echo "Or run from project root:"
	cd notebooks && source .venv/bin/activate && jupyter notebook

notebooks-clean:
	@echo "Cleaning notebook build artifacts..."
	cd notebooks && rm -rf __pycache__ .ipynb_checkpoints .pytest_cache
	cd notebooks && find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	cd notebooks && find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true
