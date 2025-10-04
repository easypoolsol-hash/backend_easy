# 🚀 Production Deployment Checklist

## ⚠️ CRITICAL: Complete ALL items before deploying to production

---

## 📋 Pre-Deployment Checklist

### 1. ✅ Environment Variables Configuration

**Location:** `infrastructure/.env` (create from `.env.example`)

#### **🔒 Security Settings (CRITICAL)**
- [ ] `SECRET_KEY` - Generate unique 50+ character secret
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(50))"
  ```
- [ ] `ENCRYPTION_KEY` - Generate 32-byte base64 encryption key
  ```bash
  python -c "import secrets; import base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
  ```
- [ ] `DEBUG=False` - **MUST be False in production**
- [ ] `ALLOWED_HOSTS` - Set your actual domain(s)
  ```
  ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,api.yourdomain.com
  ```

#### **🗄️ Database Configuration**
- [ ] `DB_NAME` - Production database name
- [ ] `DB_USER` - Dedicated database user (not root/postgres)
- [ ] `DB_PASSWORD` - Strong password (20+ chars, mixed case, numbers, symbols)
- [ ] `DB_HOST` - Database server hostname (or `db` for Docker)
- [ ] `DB_PORT` - Database port (default: 5432)

#### **🔴 Redis Configuration**
- [ ] `REDIS_URL` - Redis connection URL
- [ ] `REDIS_PASSWORD` - Set Redis password (empty means no auth!)
- [ ] `CELERY_BROKER_URL` - Celery message broker URL
- [ ] `CELERY_RESULT_BACKEND` - Celery result backend URL

#### **🐳 Docker Configuration**
- [ ] `DOCKER_USERNAME` - Your Docker Hub username
- [ ] `DOCKER_IMAGE` - Full image name (will be set by CD pipeline)

#### **🌐 CORS & Security Headers**
- [ ] `CORS_ALLOWED_ORIGINS` - Comma-separated frontend URLs
  ```
  CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
  ```
- [ ] `SECURE_SSL_REDIRECT=True` - Force HTTPS
- [ ] `SESSION_COOKIE_SECURE=True` - Secure cookies
- [ ] `CSRF_COOKIE_SECURE=True` - Secure CSRF cookies

---

### 2. ✅ GitHub Secrets Configuration

**Location:** GitHub Repository → Settings → Secrets and variables → Actions

#### **Required Secrets:**
- [ ] `DOCKER_USERNAME` - Docker Hub username
- [ ] `DOCKER_PASSWORD` - Docker Hub password or access token
- [ ] Production environment secrets (if using GitHub Environments)

---

### 3. ✅ Docker Images Available

**Check Docker Hub:**
- [ ] `latest` tag exists and is recent
- [ ] Specific commit SHA tag exists (from latest CI run)
- [ ] Images passed all CI tests
- [ ] Security scan completed without critical issues

**Verify:**
```bash
# Check available tags
docker pull your-username/bus_kiosk_backend:latest
docker pull your-username/bus_kiosk_backend:[commit-sha]
```

---

### 4. ✅ Infrastructure Server Setup

#### **Server Requirements:**
- [ ] Linux server (Ubuntu 20.04+ or similar)
- [ ] Docker installed and running
- [ ] Docker Compose installed
- [ ] Git installed (for cloning infrastructure folder)
- [ ] SSH access configured
- [ ] Firewall configured (ports 80, 443 open)

#### **Install Docker:**
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
```

---

### 5. ✅ SSL/TLS Certificates

#### **Option A: Let's Encrypt (Recommended)**
- [ ] Domain DNS configured
- [ ] Certbot installed
- [ ] Certificates generated for your domain
- [ ] Auto-renewal configured

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

#### **Option B: Custom Certificates**
- [ ] SSL certificate obtained (.crt file)
- [ ] Private key secured (.key file)
- [ ] Certificate chain included
- [ ] Certificates placed in `infrastructure/nginx/ssl/`

---

### 6. ✅ Nginx Configuration

**Location:** `infrastructure/nginx/nginx.conf`

- [ ] Server name updated with your domain
- [ ] SSL certificate paths correct
- [ ] Rate limiting configured
- [ ] Security headers enabled
- [ ] CORS headers configured
- [ ] Gzip compression enabled

---

### 7. ✅ Database Initialization

**First-time setup:**
```bash
cd infrastructure

# Start database only
docker-compose -f docker-compose.prod.yml up -d db

# Wait for database to be ready (30 seconds)
sleep 30

# Run migrations
docker-compose -f docker-compose.prod.yml run --rm web python manage.py migrate

# Create superuser
docker-compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser

# Collect static files
docker-compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
```

---

### 8. ✅ Security Hardening

#### **Django Security Settings** (Already configured in settings.py)
- [x] `DEBUG=False` (from environment)
- [x] `SECRET_KEY` from environment variable
- [x] `ENCRYPTION_KEY` from environment variable
- [x] `ALLOWED_HOSTS` from environment variable
- [x] Security middleware enabled
- [x] HTTPS/SSL enforcement
- [x] Secure cookie settings
- [x] CSRF protection enabled
- [x] XSS protection enabled

#### **Docker Security**
- [ ] Non-root user in container
- [ ] Read-only filesystem where possible
- [ ] Resource limits configured
- [ ] Security scanning completed

#### **Network Security**
- [ ] Firewall configured
- [ ] Only necessary ports exposed
- [ ] SSH key-based authentication
- [ ] Fail2ban installed (optional)

---

### 9. ✅ Monitoring & Logging

#### **Application Monitoring:**
- [ ] Health endpoint accessible: `/health/`
- [ ] Prometheus metrics enabled (optional)
- [ ] Sentry error tracking configured (optional)
- [ ] Log aggregation setup (optional)

#### **Infrastructure Monitoring:**
- [ ] Server monitoring (CPU, RAM, disk)
- [ ] Docker container monitoring
- [ ] Database monitoring
- [ ] Backup monitoring

---

### 10. ✅ Backup Strategy

#### **Database Backups:**
- [ ] Backup script configured
- [ ] Backup schedule set (daily recommended)
- [ ] Backup retention policy defined
- [ ] Backup restoration tested

```bash
# Manual backup
docker-compose -f docker-compose.prod.yml exec db pg_dump \
  -U bus_kiosk_user -d bus_kiosk_prod > backup_$(date +%Y%m%d).sql

# Restore backup
cat backup_20241004.sql | docker-compose -f docker-compose.prod.yml exec -T db \
  psql -U bus_kiosk_user -d bus_kiosk_prod
```

#### **Volume Backups:**
- [ ] PostgreSQL data volume
- [ ] Redis data volume
- [ ] Media files volume
- [ ] Log files (optional)

---

## 🚀 Deployment Steps

### Initial Deployment

1. **Clone Infrastructure:**
   ```bash
   cd /opt
   sudo mkdir bus_kiosk
   sudo chown $USER:$USER bus_kiosk
   cd bus_kiosk
   git clone https://github.com/your-username/backend_easy.git
   cd backend_easy/infrastructure
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   nano .env  # Fill in all production values
   ```

3. **Deploy Using CD Pipeline (Recommended):**
   - Go to GitHub Actions → CD Pipeline
   - Click "Run workflow"
   - Choose:
     - `deploy_target: staging` (test first)
     - `image_tag: [commit SHA from CI]`
     - `traffic_percentage: 100`
   - Verify staging works
   - Deploy to production (blue/green)

4. **Manual Deployment (Alternative):**
   ```bash
   cd infrastructure
   ./deploy.sh
   ```

5. **Verify Deployment:**
   ```bash
   # Check all services running
   docker-compose -f docker-compose.prod.yml ps

   # Check logs
   docker-compose -f docker-compose.prod.yml logs -f web

   # Test health endpoint
   curl http://your-domain.com/health/
   ```

---

## 🔄 Post-Deployment Checklist

### **Immediate Verification (First 10 minutes)**
- [ ] All containers running: `docker ps`
- [ ] Health endpoint responding: `curl http://domain/health/`
- [ ] Admin panel accessible: `https://domain/admin/`
- [ ] API endpoints responding
- [ ] No critical errors in logs

### **Extended Monitoring (First Hour)**
- [ ] Database connections stable
- [ ] Redis cache working
- [ ] Celery workers processing tasks
- [ ] No memory/CPU spikes
- [ ] Response times acceptable

### **Business Validation (First Day)**
- [ ] User authentication working
- [ ] Core API features functional
- [ ] File uploads working
- [ ] Background tasks processing
- [ ] Email notifications sent (if applicable)

---

## 🆘 Rollback Procedure

### **Quick Rollback (Blue-Green):**
If using blue-green deployment:
```bash
# Switch traffic back to previous environment
# In load balancer or via CD pipeline:
deploy_target: green  # Switch to opposite environment
```

### **Version Rollback:**
```bash
# Deploy previous working version
docker-compose -f docker-compose.prod.yml down
export DOCKER_IMAGE=your-username/bus_kiosk_backend:[previous-commit-sha]
docker-compose -f docker-compose.prod.yml up -d
```

### **Emergency Database Rollback:**
```bash
# Restore from backup
cat backup_YYYYMMDD.sql | docker-compose -f docker-compose.prod.yml exec -T db \
  psql -U bus_kiosk_user -d bus_kiosk_prod
```

---

## 📞 Support Contacts

- **DevOps Lead:** [Name/Email]
- **Database Admin:** [Name/Email]
- **Security Team:** [Name/Email]
- **On-Call Engineer:** [Phone/Pager]

---

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [OWASP Security Guidelines](https://owasp.org/www-project-web-security-testing-guide/)
- [Let's Encrypt Setup](https://letsencrypt.org/getting-started/)

---

## ✅ Final Sign-Off

**Before going live, confirm:**
- [ ] All checklist items completed
- [ ] Security review passed
- [ ] Load testing completed (if required)
- [ ] Backup and restore tested
- [ ] Rollback procedure tested
- [ ] Team trained on deployment process
- [ ] Documentation up to date
- [ ] Monitoring and alerts configured

**Deployment Date:** _______________
**Deployed By:** _______________
**Reviewed By:** _______________
**Approved By:** _______________

---

**🎉 Ready for Production!**

Remember: Production deployments should be boring and predictable. If something feels rushed or unclear, STOP and clarify before proceeding.
