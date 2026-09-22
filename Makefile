.PHONY: help run bench seed docker-up docker-down clean lint format type-check test test-cov ci dev-up

# Environment detection: prefer active virtualenv binaries if present, otherwise PATH
PYTHON    := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
RUFF      := $(if $(wildcard .venv/bin/ruff),.venv/bin/ruff,ruff)
MYPY      := $(if $(wildcard .venv/bin/mypy),.venv/bin/mypy,mypy)
PYTEST    := $(if $(wildcard .venv/bin/pytest),.venv/bin/pytest,pytest)
STREAMLIT := $(if $(wildcard .venv/bin/streamlit),.venv/bin/streamlit,streamlit)
UVICORN   := $(if $(wildcard .venv/bin/uvicorn),.venv/bin/uvicorn,uvicorn)

help:
	@echo "PortalPulse Enterprise CLI & Engineering Standard Targets:"
	@echo "  make lint        - Run Ruff linting check across repo"
	@echo "  make format      - Format codebase using Ruff"
	@echo "  make type-check  - Run Mypy strict type checking on backend/"
	@echo "  make test        - Run full pytest test suite"
	@echo "  make test-cov    - Run pytest with terminal and HTML coverage report"
	@echo "  make ci          - Run lint, type-check, and test-cov (full local CI check)"
	@echo "  make dev-up      - Launch FastAPI Control Tower API server (port 8000)"
	@echo "  make run         - Launch Streamlit Control Tower Dashboard (port 8501)"
	@echo "  make bench       - Run Redis vs SQLite benchmark"
	@echo "  make seed        - Populate local SQLite DB with synthetic student records"
	@echo "  make docker-up   - Build and start containers with Docker Compose"
	@echo "  make docker-down - Teardown running Docker containers"
	@echo "  make clean       - Remove cached bytecode and coverage artifacts"

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

type-check:
	$(MYPY) --strict backend/

test:
	$(PYTEST) tests/

test-cov:
	$(PYTEST) --cov=backend --cov-report=term-missing --cov-report=html:coverage_html --cov-fail-under=80 tests/

ci: lint type-check test-cov

dev-up:
	$(UVICORN) backend.app:app --host 0.0.0.0 --port 8000 --reload

run:
	$(STREAMLIT) run dashboard/app.py --server.port 8501

bench:
	$(PYTHON) scripts/benchmark_cache.py 80

seed:
	$(PYTHON) scripts/seed_database.py 200

docker-up:
	docker-compose up -d --build

docker-down:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache .mypy_cache coverage_html .coverage htmlcov
