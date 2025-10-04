# Local Development with Docker

This guide explains how to run the Bus Kiosk Backend locally using Docker for development and testing.

## 🚀 Quick Start

### Prerequisites
- Docker Desktop installed and running
- Docker Compose v2.0+

### 1. Clone and Setup
```bash
git clone https://github.com/easypoolsol-hash/backend_easy.git
cd backend_easy
```

### 2. Environment Setup
The `.env` file is already configured for local Docker development with:
- PostgreSQL database
- Redis cache/message broker
- Django debug mode enabled

### 3. Start Services
```bash
# Start all services (Django + PostgreSQL + Redis + Nginx + Celery)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 4. Access the Application
- **Web App**: http://localhost
- **API Docs**: http://localhost/docs/
- **Health Check**: http://localhost/health/
- **Database**: localhost:5432 (from host machine)

## 🏗️ Architecture

The local setup includes:

- **web**: Django application (Gunicorn server)
- **db**: PostgreSQL 15 database
- **redis**: Redis cache & message broker
- **nginx**: Reverse proxy & static file serving
- **celery_worker**: Background task processing
- **celery_beat**: Scheduled task management

## 🛠️ Development Workflow

### Running Django Commands
```bash
# Access Django shell in container
docker-compose exec web python manage.py shell

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Run tests
docker-compose exec web python manage.py test
```

### Database Management
```bash
# Access PostgreSQL shell
docker-compose exec db psql -U bus_kiosk_user -d bus_kiosk

# Reset database (remove volumes and recreate)
docker-compose down -v
docker-compose up -d db
docker-compose exec web python manage.py migrate
```

### Logs & Debugging
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f web
docker-compose logs -f db
docker-compose logs -f redis

# Check container status
docker-compose ps
```

## 🔧 Configuration

### Environment Variables
Key variables in `.env`:
- `DEBUG=True` - Django debug mode
- `DB_*` - PostgreSQL connection settings
- `REDIS_URL` - Redis connection
- `ALLOWED_HOSTS` - CORS and host settings

### Customizing Services
Edit `docker-compose.yml` to:
- Change ports
- Add volume mounts
- Modify environment variables
- Add new services

## 🧪 Testing

### Run Tests in Docker
```bash
# Run all tests
docker-compose exec web python manage.py test

# Run specific tests
docker-compose exec web python manage.py test users.tests
```

### API Testing
```bash
# Test health endpoint
curl http://localhost/health/

# Test API endpoints
curl http://localhost/api/students/
```

## 🚀 Deployment

When ready for production:
1. Use the infrastructure folder for production deployment
2. CI/CD pipelines handle automated deployment
3. Blue-green deployments with canary traffic control

See `infrastructure/README.md` for production deployment details.

## 🐛 Troubleshooting

### Common Issues

**Port conflicts:**
```bash
# Check what's using ports
netstat -ano | findstr :5432
netstat -ano | findstr :6379
netstat -ano | findstr :80

# Change ports in docker-compose.yml if needed
```

**Database connection issues:**
```bash
# Check database logs
docker-compose logs db

# Reset database
docker-compose down -v
docker-compose up -d db
```

**Application not starting:**
```bash
# Check Django logs
docker-compose logs web

# Check if database is ready
docker-compose exec db pg_isready -U bus_kiosk_user -d bus_kiosk
```

### Clean Restart
```bash
# Stop everything and clean up
docker-compose down -v --remove-orphans

# Rebuild and start fresh
docker-compose up -d --build
```

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Django Documentation](https://docs.djangoproject.com/)
- [PostgreSQL Docker Image](https://hub.docker.com/_/postgres)
- [Redis Docker Image](https://hub.docker.com/_/redis)</content>
<parameter name="filePath">c:\Users\lalit\OneDrive\Desktop\Imperial_easypool\backend_easy\DEVELOPMENT.md
