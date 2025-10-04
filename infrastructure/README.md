# Infrastructure - Continuous Deployment (CD)

This folder contains the **Continuous Deployment (CD)** infrastructure for the Bus Kiosk Backend application. It follows the industry best practice of separating CI (build/test) from CD (deploy), where CI creates immutable artifacts and CD deploys them to various environments.

## 🎯 Blue-Green Deployment Strategy

The CI/CD pipeline now supports **Blue-Green deployments** for zero-downtime releases:

- **🔵 Blue Environment**: Current production serving live traffic
- **🟢 Green Environment**: New deployment being prepared
- **🚀 Traffic Switch**: Instant switch when Green is healthy
- **🔄 Instant Rollback**: Blue environment always available

### Quick Blue-Green Deploy

```bash
# Deploy to Green environment (canary mode - send 20% traffic first)
gh workflow run "CD Pipeline - Blue-Green Deployment" \
  -f deploy_target=green \
  -f traffic_percentage=20

# Full production switch to Green (after testing canary)
gh workflow run "CD Pipeline - Blue-Green Deployment" \
  -f deploy_target=green \
  -f traffic_percentage=100

# Instant rollback to Blue
gh workflow run "CD Pipeline - Blue-Green Deployment" \
  -f deploy_target=blue \
  -f traffic_percentage=100
```

📖 **[Complete Blue-Green Guide](BLUE_GREEN_DEPLOYMENT.md)**

### **🎯 Canary Deployments**

**Gradual Traffic Rollout**: Safely test new deployments with partial traffic:

- **10-25% Traffic**: Initial canary testing with real users
- **50-75% Traffic**: Gradual rollout after monitoring
- **100% Traffic**: Full production switch
- **Instant Rollback**: Switch back to previous version immediately

**Benefits:**
- 🛡️ **Risk Reduction**: Catch issues before full rollout
- 📊 **Real User Testing**: Monitor performance with actual traffic
- 🔄 **Zero-Downtime Rollback**: Switch traffic instantly if problems occur
- 📈 **Gradual Adoption**: Slowly increase exposure to new features

### **🐳 Docker Hub Free Tier Compatible**

**Single Repository Strategy**: Uses one Docker Hub repository with multiple tags:

```
your-username/bus_kiosk_backend
├── :blue     ← Blue environment
├── :green    ← Green environment
├── :staging  ← Staging environment
└── :latest   ← Latest build
```

**Benefits:**
- ✅ **Free Tier Compatible**: No additional repositories needed
- ✅ **Cost Effective**: Single private repository
- ✅ **Simple Management**: One repository to maintain
- ✅ **Zero-Downtime**: Blue-green deployments
- ✅ **Safe Rollouts**: Canary deployments with traffic control
- ✅ **Instant Rollback**: Always have a working environment available

### Tag Management

Use the included tag manager script:

```bash
# Set your Docker Hub username
export DOCKER_USERNAME=your-username

# Check status
./blue-green-manager.sh status

# Promote latest to green
./blue-green-manager.sh promote latest green

# Switch active environment
./blue-green-manager.sh switch green
```

## 🏗️ Architecture Overview

**✅ SEPARATED CI/CD APPROACH:**

- **CI Pipeline** (`../.github/workflows/ci-cd.yml`): Builds, tests, and pushes Docker images only
- **CD Pipeline** (`infrastructure/.github/workflows/cd.yml`): Deploys pre-built images to production environments
- **Immutable Infrastructure**: Application code is built once, deployed many times
- **Clean Separation**: Build artifacts are separate from deployment logic

```
CI Pipeline (Build/Test) → Docker Hub Registry → CD Pipeline (Deploy)
     ↓                                                    ↓
  Quality Gates                                      Production Environment
  - Tests                                             - Image Pull
  - Security Scans                                   - Service Orchestration
  - Image Build/Push                                 - Health Checks
```

## 📁 Directory Structure

```text
backend_easy/
├── .github/workflows/ci-cd.yml     # CI Pipeline (build/test)
├── Dockerfile                      # Build recipe (used by CI)
├── infrastructure/                 # CD Infrastructure (this folder)
│   ├── deploy.sh                   # Automated deployment script
│   ├── .github/workflows/cd.yml    # CD Pipeline workflow
│   ├── docker-compose.prod.yml     # Production orchestration
│   ├── .env.example               # Environment template
│   ├── nginx/
│   │   └── nginx.conf             # Production web server config
│   └── README.md                  # This documentation
└── ...source code...              # Application code (not needed in production)
```

## 🚀 Deployment Options

### Option 1: Automated CD Pipeline (Recommended)

The CD pipeline supports **Blue-Green deployments** with **Canary traffic control**:

1. **Automatic Trigger**: Runs after CI pipeline succeeds on master/main
2. **Manual Trigger**: Via GitHub Actions workflow dispatch
3. **Blue-Green Deployment**: Zero-downtime deployments with instant rollback
4. **Canary Deployments**: Gradual traffic rollout (1-100% of traffic)
5. **Health Checks**: Automatic validation after deployment

#### Manual CD Trigger

1. Go to GitHub Actions → "CD Pipeline - Blue-Green Deployment"
2. Click "Run workflow"
3. Choose deployment target:
   - `blue` or `green` for blue-green deployment
   - `staging` or `production` for direct deployment
4. Set traffic percentage (1-100%, default 100%)
5. Enable force deploy if needed

#### Deployment Strategies

**🔵🟢 Blue-Green Deployment:**
```bash
# Deploy to Green with 25% traffic (canary)
gh workflow run "CD Pipeline - Blue-Green Deployment" \
  -f deploy_target=green \
  -f traffic_percentage=25

# Full switch to Green after testing
gh workflow run "CD Pipeline - Blue-Green Deployment" \
  -f deploy_target=green \
  -f traffic_percentage=100

# Instant rollback to Blue
gh workflow run "CD Pipeline - Blue-Green Deployment" \
  -f deploy_target=blue \
  -f traffic_percentage=100
```

**🎯 Canary Deployment:**
- Start with 10-25% traffic to new deployment
- Monitor metrics and logs
- Gradually increase traffic (50%, 75%, 100%)
- Rollback instantly if issues detected

### Option 2: Manual Deployment Script

For direct server deployment or custom scenarios:

```bash
# On your production server
cd /opt/bus_kiosk/infrastructure

# Make script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

## 📋 Prerequisites

### Server Requirements

- **OS**: Ubuntu 20.04+ or Debian 11+
- **Docker**: >= 20.10 with Docker Compose v2
- **Network**: Domain name pointing to server
- **Security**: SSH key-based access, firewall configured

### Environment Setup

```bash
# Create deployment directory
sudo mkdir -p /opt/bus_kiosk && cd /opt/bus_kiosk

# Clone infrastructure code
git clone --depth 1 --branch main \
    https://github.com/your-org/backend_easy.git \
    temp && mv temp/infrastructure/* . && rm -rf temp

# Set up environment
cp .env.example .env
nano .env  # Configure your production variables
```

## ⚙️ Environment Configuration

### Required Environment Variables

Create a `.env` file with these variables:

```bash
# Database Configuration
DB_NAME=bus_kiosk_prod
DB_USER=bus_kiosk_user
DB_PASSWORD=your_secure_db_password
DB_HOST=db
DB_PORT=5432

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Django Settings
SECRET_KEY=your-50-character-django-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com,www.yourdomain.com

# Docker Registry
DOCKER_USERNAME=your-dockerhub-username

# SSL/TLS (if using custom certificates)
SSL_CERT_PATH=/path/to/ssl/cert.pem
SSL_KEY_PATH=/path/to/ssl/private.key
```

### SSL Certificates

For production HTTPS, place certificates in `nginx/ssl/`:

```bash
mkdir -p nginx/ssl
# Copy your certificates
cp /path/to/cert.pem nginx/ssl/
cp /path/to/private.key nginx/ssl/
```

## 🔄 Deployment Process

The deployment script (`deploy.sh`) performs these steps:

1. **Prerequisites Check**: Validates Docker, Docker Compose, environment
2. **Image Pull**: Downloads latest application image from Docker Hub
3. **Database Backup**: Creates timestamped backup (optional)
4. **Service Stop**: Gracefully stops current services
5. **Service Start**: Starts new services with updated image
6. **Health Check**: Validates application health endpoints
7. **Cleanup**: Removes old Docker resources

### Deployment Commands

```bash
# Full deployment
./deploy.sh

# Individual steps (for debugging)
./deploy.sh check    # Prerequisites check
./deploy.sh pull     # Pull images only
./deploy.sh backup   # Database backup only
./deploy.sh start    # Start services only
./deploy.sh health   # Health check only
```

## 🔍 Monitoring & Health Checks

### Application Health

```bash
# Health endpoint
curl -f https://yourdomain.com/health/

# Detailed health check
curl -f https://yourdomain.com/health/?detailed=1
```

### Service Monitoring

```bash
# Service status
docker-compose -f docker-compose.prod.yml ps

# Resource usage
docker stats

# Service logs
docker-compose -f docker-compose.prod.yml logs -f web
docker-compose -f docker-compose.prod.yml logs -f nginx
```

### Log Aggregation

```bash
# Application logs
docker-compose -f docker-compose.prod.yml exec web tail -f /app/logs/django.log

# Nginx access logs
docker-compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/access.log

# Nginx error logs
docker-compose -f docker-compose.prod.yml exec nginx tail -f /var/log/nginx/error.log
```

## � Maintenance Operations

### Service Management

```bash
# Restart all services
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart web

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale web=3
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=2
```

### Database Operations

```bash
# Create backup
docker-compose -f docker-compose.prod.yml exec db \
    pg_dump -U bus_kiosk_user -d bus_kiosk_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker-compose -f docker-compose.prod.yml exec -T db \
    psql -U bus_kiosk_user -d bus_kiosk_prod < backup.sql

# Database shell
docker-compose -f docker-compose.prod.yml exec db \
    psql -U bus_kiosk_user -d bus_kiosk_prod
```

### Updates & Rollbacks

```bash
# Update to latest image
docker pull your-dockerhub-username/bus_kiosk_backend:latest
docker-compose -f docker-compose.prod.yml up -d web

# Rollback to specific version
docker pull your-dockerhub-username/bus_kiosk_backend:v1.2.3
docker-compose -f docker-compose.prod.yml up -d web
```

## 🔒 Security Considerations

### Production Security Checklist

- [ ] **Secrets Management**: Use GitHub Secrets or external secret managers
- [ ] **Network Security**: Configure firewall (UFW, firewalld)
- [ ] **SSL/TLS**: Valid certificates with proper renewal
- [ ] **Access Control**: SSH key-only access, sudo restrictions
- [ ] **Updates**: Regular Docker image and system updates
- [ ] **Monitoring**: Log aggregation and alerting setup
- [ ] **Backups**: Automated database and configuration backups

### SSL/TLS Configuration

- Use TLS 1.2+ only
- Configure HSTS headers
- Regular certificate renewal (Let's Encrypt recommended)
- Strong cipher suites

## 🚨 Troubleshooting

### Common Issues & Solutions

1. **Deployment Fails at Pull**
   ```bash
   # Check Docker Hub credentials
   docker login

   # Verify image exists
   docker pull your-username/bus_kiosk_backend:latest
   ```

2. **Database Connection Issues**
   ```bash
   # Check database logs
   docker-compose -f docker-compose.prod.yml logs db

   # Test connection
   docker-compose -f docker-compose.prod.yml exec web python manage.py dbshell
   ```

3. **Application Not Responding**
   ```bash
   # Check application logs
   docker-compose -f docker-compose.prod.yml logs web

   # Test health endpoint
   curl -v https://yourdomain.com/health/
   ```

4. **SSL Certificate Problems**
   ```bash
   # Check certificate validity
   openssl x509 -in nginx/ssl/cert.pem -text -noout

   # Test SSL configuration
   openssl s_client -connect yourdomain.com:443
   ```

### Debug Commands

```bash
# System resources
docker system df
docker system info

# Container inspection
docker inspect $(docker-compose -f docker-compose.prod.yml ps -q web)

# Network debugging
docker network ls
docker network inspect bus_kiosk_default

# Volume inspection
docker volume ls
docker volume inspect bus_kiosk_postgres_data
```

## � Performance Optimization

### Scaling Considerations

```bash
# Horizontal scaling (multiple web containers)
docker-compose -f docker-compose.prod.yml up -d --scale web=3

# Database connection pooling
# Configure in Django settings for high traffic

# Redis clustering
# For high-availability Redis setup
```

### Resource Limits

Configure resource limits in `docker-compose.prod.yml`:

```yaml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## 🤝 Contributing

### Infrastructure Changes

1. **Test Locally**: Use Docker Compose for local testing
2. **Documentation**: Update this README for any changes
3. **Staging First**: Test in staging environment before production
4. **Version Control**: Tag infrastructure changes appropriately
5. **Security Review**: Review security implications of changes

### Adding New Environment Variables

1. Add to `.env.example` with documentation
2. Update `docker-compose.prod.yml` if needed
3. Update this README
4. Test in all environments

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [Django Deployment Guide](https://docs.djangoproject.com/en/stable/howto/deployment/)
- [PostgreSQL Docker Image](https://hub.docker.com/_/postgres)
- [Redis Docker Image](https://hub.docker.com/_/redis)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## 🆘 Support

For issues:

- **CI Pipeline Issues**: Check `../.github/workflows/ci-cd.yml` logs
- **CD Pipeline Issues**: Check `infrastructure/.github/workflows/cd.yml` logs
- **Application Issues**: Check application logs and health endpoints
- **Infrastructure Issues**: Review this documentation and deployment logs
- **Security Issues**: Contact security team immediately
 
 
