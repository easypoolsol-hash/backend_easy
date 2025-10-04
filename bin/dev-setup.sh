#!/bin/bash
# Local Development Setup
# Usage: ./bin/dev-setup.sh

set -e

echo "🚀 Setting up local development environment..."
echo ""

# Navigate to project root
cd "$(dirname "$0")/.." || exit 1

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found"
    if [ -f ".env.example" ]; then
        echo "📋 Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  Please update .env with your local settings"
    else
        echo "❌ No .env.example found. Cannot create .env"
        exit 1
    fi
fi

# Start Docker services
echo "🐳 Starting Docker services..."
docker-compose up -d db redis

echo "⏳ Waiting for services to be ready..."
sleep 5

# Navigate to app directory
cd app || exit 1

# Install Python dependencies
echo "📦 Installing Python dependencies..."
python -m pip install --upgrade pip
pip install -e .[dev,testing]

# Run migrations
echo "🔄 Running migrations..."
python manage.py migrate

# Create superuser (optional)
read -p "Create superuser? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python manage.py createsuperuser
fi

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Review .env file and update if needed"
echo "   2. Run: cd app && python manage.py runserver"
echo "   3. Visit: http://localhost:8000"
