.PHONY: dev

PORT ?= 8010
HOST ?= 127.0.0.1
PYTHON ?= .venv/bin/python

dev:
	$(PYTHON) -m uvicorn app.main:app --reload --host $(HOST) --port $(PORT)
