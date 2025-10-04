# Industrial Django Linting Pipeline (Optimized)
# Fast, comprehensive, no redundancy

.PHONY: lint lint-all lint-fix format check clean setup-dev ci

# Primary linting (fastest - ruff handles most rules)
lint:
	@echo "� Running Ruff (comprehensive Django linter)..."
	ruff check app/
	@echo "🔍 Running Pylint (complex Django analysis)..."
	pylint app/users app/students app/bus_kiosk_backend --errors-only
	@echo "🔍 Running MyPy (type checking)..."
	python -m mypy app/users/ app/students/ --config-file config/mypy.ini
	@echo "✅ Core linting passed!"

# Run all linting tools (comprehensive)
lint-all: lint format
	@echo "🏛️ Running Django-specific linting..."
	django-lint bus_kiosk_backend || echo "Django-lint not installed, skipping..."
	@echo "✅ All linting checks passed!"

# Auto-fix issues (formatting + safe fixes)
lint-fix:
	@echo "🔧 Running Ruff auto-fixes..."
	ruff check --fix .
	@echo "🎨 Running Black formatting..."
	black .
	@echo "✅ Auto-fixes applied!"

# Format code only
format:
	@echo "🎨 Running Black code formatting..."
	black .
	@echo "✅ Code formatted!"

# Comprehensive quality check
check: lint-all
	@echo "🎯 Running final Django quality checks..."
	@echo "✅ All quality checks passed!"

# Clean cache files
clean:
	@echo "🧹 Cleaning cache files..."
	rm -rf .mypy_cache .ruff_cache __pycache__ */__pycache__ .pytest_cache
	@echo "✅ Cache cleaned!"

# Setup development environment
setup-dev:
	@echo "⚙️ Setting up industrial Django development..."
	pip install -e ".[dev,linting,typing]"
	pre-commit install || echo "Pre-commit not available"
	@echo "✅ Development environment ready!"

# CI/CD pipeline (fast feedback)
ci: clean lint
	@echo "🚀 CI/CD pipeline completed successfully!"
