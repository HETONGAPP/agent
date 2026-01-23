# Makefile for BESS Agent

.PHONY: help install test run collect docker-up docker-down clean setup-grafana test-agent start stop status

help:
	@echo "BESS Agent project commands:"
	@echo ""
	@echo "Service Management:"
	@echo "  make start          - Start Agent service"
	@echo "  make stop           - Stop Agent service"
	@echo "  make status         - Check system health"
	@echo "  make run            - Start Agent service (alias for start)"
	@echo ""
	@echo "Setup & Configuration:"
	@echo "  make install        - Install dependencies"
	@echo "  make setup-grafana  - Setup Grafana (data source and dashboard)"
	@echo ""
	@echo "Testing & Data:"
	@echo "  make test           - Run unit tests"
	@echo "  make test-agent     - Run Agent test suite"
	@echo "  make collect        - Run data collection script"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      - Start Docker services"
	@echo "  make docker-down    - Stop Docker services"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          - Clean temporary files"
	@echo ""
	@echo "Note: You can also use 'python scripts/agent.py <command>' for more options"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

run: start

start:
	python scripts/agent.py start

stop:
	python scripts/agent.py stop

status:
	python scripts/agent.py status

collect:
	python scripts/agent.py collect

docker-up:
	cd docker && docker compose up -d

docker-down:
	cd docker && docker compose down

setup-grafana:
	python scripts/agent.py setup-grafana

test-agent:
	python scripts/agent.py test

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
