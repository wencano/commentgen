.PHONY: dev setup test

PORT ?= 8010
HOST ?= 127.0.0.1
# Use python3: on Linux, `python` in a venv can be a broken symlink; recreate venv on this host if you see "No such file" (do not rsync .venv)
PYTHON ?= .venv/bin/python3
# Override: `make setup PY=python3.12`
PY ?= python3

setup:
	$(PY) -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -r requirements.txt

dev:
	$(PYTHON) -m uvicorn app.main:app --reload --host $(HOST) --port $(PORT)

test:
	$(PYTHON) -m unittest discover -s tests -v
