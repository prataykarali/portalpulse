.PHONY: run test bench seed docker-up docker-down clean

run:
	./.venv/bin/streamlit run dashboard/app.py --server.port 8501

test:
	./.venv/bin/python -m unittest discover -s tests

bench:
	./.venv/bin/python scripts/benchmark_cache.py 80

seed:
	./.venv/bin/python scripts/seed_database.py 200

docker-up:
	docker-compose up -d --build

docker-down:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
