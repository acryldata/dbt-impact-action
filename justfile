
test: lint
	# TODO

setup:
	# Create venv.
	python3 -m venv venv
	venv/bin/pip install --upgrade pip wheel setuptools
	venv/bin/pip install -r requirements.txt -r requirements-dev.txt

lint:
	venv/bin/black --check .
	venv/bin/ruff .
	venv/bin/mypy .

lint-fix:
	venv/bin/black .
	venv/bin/ruff .
	venv/bin/mypy .
