
test: lint
	venv/bin/pytest tests

setup:
	# Create venv.
	python3 -m venv venv
	source venv/bin/activate
	pip install --upgrade uv
	uv pip install --upgrade pip wheel setuptools
	uv pip install -r requirements.txt -r requirements-dev.txt

lint:
	source venv/bin/activate
	black --check .
	ruff check .
	mypy .

lint-fix:
	source venv/bin/activate
	black .
	ruff check --fix .
	ruff format .
	mypy .
