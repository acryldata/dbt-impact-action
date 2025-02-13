
test: lint
	venv/bin/pytest tests

setup:
	# Create venv.
	python3 -m venv venv
	venv/bin/pip install --upgrade uv
	venv/bin/uv pip install --upgrade pip wheel setuptools
	venv/bin/uv pip install -r requirements.txt -r requirements-dev.txt

lint:
	venv/bin/black --check .
	venv/bin/ruff check .
	venv/bin/mypy .

lint-fix:
	venv/bin/black .
	venv/bin/ruff check --fix .
	venv/bin/ruff format .
	venv/bin/mypy .
