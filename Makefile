.PHONY: help run run-fresh migrate seed test clean

# Default target - show help
help:
	@echo "🚀 Imperial EasyPool Backend - Easy Commands"
	@echo "============================================="
	@echo ""
	@echo "QUICK START:"
	@echo "  make run           - Start Django development server"
	@echo "  make run-fresh     - Fresh start (migrate + seed + run)"
	@echo ""
	@echo "DATABASE:"
	@echo "  make migrate       - Run database migrations"
	@echo "  make seed          - Seed database with test data"
	@echo ""
	@echo "TESTING:"
	@echo "  make test          - Run all tests"
	@echo ""
	@echo "CLEANUP:"
	@echo "  make clean         - Clean Python cache files"
	@echo ""
	@echo "Backend will run on: http://localhost:8000"
	@echo "Admin panel: http://localhost:8000/admin"
	@echo "Default credentials: admin / admin123"

# Start Django ASGI development server (supports WebSockets)
run:
	@echo "Starting Django ASGI development server..."
	@echo "Backend: http://localhost:8000"
	@echo "Admin: http://localhost:8000/admin"
	@call .venv\Scripts\activate.bat && cd app && set DJANGO_ENV=local && daphne -b 0.0.0.0 -p 8000 bus_kiosk_backend.asgi:application

# Fresh start: migrate + seed + run
run-fresh:
	@echo "Fresh backend startup..."
	@call .venv\Scripts\activate.bat && cd app && python manage.py migrate
	@call .venv\Scripts\activate.bat && cd app && python manage.py seed_groups
	@call .venv\Scripts\activate.bat && cd app && python manage.py seed_all
	@echo "✅ Database ready!"
	@echo "Starting server..."
	@call .venv\Scripts\activate.bat && cd app && set DJANGO_ENV=local && daphne -b 0.0.0.0 -p 8000 bus_kiosk_backend.asgi:application

# Run database migrations
migrate:
	@echo "Running database migrations..."
	@call .venv\Scripts\activate.bat && cd app && python manage.py migrate
	@echo "✅ Migrations complete!"

# Seed database with test data
seed:
	@echo "Seeding database with test data..."
	@call .venv\Scripts\activate.bat && cd app && python manage.py seed_groups
	@call .venv\Scripts\activate.bat && cd app && python manage.py seed_all
	@echo "✅ Database seeded!"

# Run tests
test:
	@echo "Running tests..."
	@call .venv\Scripts\activate.bat && cd app && python manage.py test
	@echo "✅ Tests complete!"

# Clean Python cache files
clean:
	@echo "Cleaning Python cache..."
	@cd app && del /s /q *.pyc 2>nul
	@cd app && for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
	@echo "✅ Cache cleaned!"
