# Makefile for verb-gloss-wsd

UV=uv
FIND=find
MAKE=make
SRC=aidu.support
APP=app/

.PHONY: help install clean wipe serve run smoke test curl web.build

help:                              ## Show this help
	@grep -h "##" $(MAKEFILE_LIST) | grep -v grep | sed -e "s/\$$//" -e "s/##//"

# install targets

install:                           ## Install python dependencies and set up environment
	@echo "Installing dependencies"
	@$(UV) sync

	@echo "Upgrading pip"
	@$(UV) run python -m ensurepip --upgrade

# Cleanup targets

clean:                             ## Clean temporary and cache files
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .venv
	$(FIND) . -type f -name '*~' -delete
	$(FIND) . -type f -name '*.pyc' -delete
	$(FIND) . -type d -name '__pycache__' -delete

wipe:                              ## Delete all uv-related files for a fresh start
wipe: clean
	@echo "Removing uv.lock"
	rm -f uv.lock

# Testing targets
	
test:                              ## Run all tests
	@echo "Running tests..."
	$(UV) run pytest tests/

publish:                           ## Publish the package to PyPI
	@echo "Publishing package..."
	@source ~/.env && uv publish --token "$$PYPI_TOKEN"

# Tutorial targets

jupyter:                           ## Start a jupyter notebook server
	@if [ ! -d ".venv" ]; then uv venv; fi
	uv pip install jupyter
	uv run jupyter lab

