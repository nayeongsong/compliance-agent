.PHONY: help install extract evaluate lint format check clean

help:
	@echo "Usage:"
	@echo "  make install                         - install deps into .venv (via uv)"
	@echo "  make extract                         - extract rules -> data/processed/rules.json"
	@echo "  make evaluate FILE=path/to/copy.txt  - evaluate marketing copy from a file"
	@echo "  make evaluate TEXT='short copy'       - evaluate a short inline string"
	@echo "  make lint                            - ruff check"
	@echo "  make format                          - ruff format"
	@echo "  make check                           - lint + format check"
	@echo "  make clean                           - remove generated rules"
	@echo ""
	@echo "  Or run the script directly:"
	@echo "  uv run scripts/check_compliance.py --text 'Your copy here'"
	@echo "  uv run scripts/check_compliance.py --file path/to/copy.txt"

install:
	uv sync

extract:
	uv run scripts/extract_rules.py

evaluate:
ifdef FILE
	uv run scripts/check_compliance.py --file "$(FILE)"
else ifdef TEXT
	uv run scripts/check_compliance.py --text "$(TEXT)"
else
	@uv run scripts/check_compliance.py
endif

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check .
	uv run ruff format --check .

clean:
	rm -f data/processed/rules.json
