
test: lint
	venv/bin/pytest tests

setup:
	# Create venv.
	pip install --upgrade uv
	uv venv venv --python 3.10
	. venv/bin/activate
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
