.PHONY: setup test lint backtest docker-build docker-backtest clean

setup:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

backtest:
	gridq backtest examples/bundles/pv_battery_tou

docker-build:
	docker build -t gridq-engine:latest .

docker-backtest:
	docker run --rm -v $(PWD)/examples:/app/examples gridq-engine:latest gridq backtest examples/bundles/pv_battery_tou

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/ *.egg-info
	rm -rf examples/bundles/*/outputs/
	rm -rf examples/bundles/*/dispatch.parquet
	rm -rf examples/bundles/*/solve_stats.json
	rm -rf examples/bundles/*/metrics.json
