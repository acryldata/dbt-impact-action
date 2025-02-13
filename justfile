
test: lint
	pytest tests

setup:
	uv pip install --upgrade pip wheel setuptools
	uv pip install -r requirements.txt -r requirements-dev.txt

lint:
	. venv/bin/activate
	black --check .
	ruff check .
	mypy .

lint-fix:
	black .
	ruff check --fix .
	ruff format .
	mypy .
