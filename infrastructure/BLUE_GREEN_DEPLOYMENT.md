# Blue-Green Deployment Strategy

This document explains the Blue-Green deployment strategy implemented in the Bus Kiosk Backend CI/CD pipeline.

## 🎯 What is Blue-Green Deployment?

Blue-Green deployment is a deployment strategy that reduces downtime and risk by running two identical production environments:

- **🔵 Blue Environment**: Current production environment serving live traffic
- **🟢 Green Environment**: New deployment environment being prepared
- **🚀 Traffic Switch**: When Green is ready and healthy, traffic switches from Blue to Green
- **🔄 Rollback**: Blue environment remains available for instant rollback

## 🐳 Docker Hub Free Tier Strategy

**Docker Hub Free Tier Limitation**: Only 1 private repository allowed.

### **Solution: Tags Within Single Repository**

Instead of separate repositories, we use **tags within one repository**:

```
your-username/bus_kiosk_backend
├── :blue     ← Blue environment image
├── :green    ← Green environment image
├── :staging  ← Staging environment image
├── :latest   ← Latest build
└── :abc123   ← Git commit SHA
```

### **How It Works**

1. **Single Repository**: `your-username/bus_kiosk_backend`
2. **Multiple Tags**: Different tags for different environments
3. **Same Image**: All tags reference the same repository
4. **Free Tier Compliant**: No additional repositories needed

### **Tag Strategy**

| Environment | Tag | Purpose |
|-------------|-----|---------|
| Blue | `:blue` | Current production |
| Green | `:green` | New deployment |
| Staging | `:staging` | Testing environment |
| Latest | `:latest` | Most recent build |
| Commit | `:abc123` | Specific git commit |

### **Deployment Flow**

```
Build Image → Tag as :blue/:green/:staging → Deploy Specific Tag
     ↓                ↓                        ↓
  CI Pipeline     Single Repository        Environment Specific
```

### **Benefits**

- ✅ **Free Tier Compatible**: Uses one repository with multiple tags
- ✅ **Cost Effective**: No additional Docker Hub costs
- ✅ **Simple Management**: Single repository to maintain
- ✅ **Version Control**: Each deployment has its own tag

## 🏗️ Architecture

```
Internet
    ↓
Load Balancer (nginx/AWS ALB/etc.)
    ↓
Active Environment (Blue or Green)
    ↓
Application Servers
    ↓
Database & Redis
```

## 🚀 Deployment Flow

### 1. **Normal Operation**
- Blue environment serves 100% of traffic
- Green environment is idle or running previous version

### 2. **Deployment Trigger**
```bash
# Manual deployment to Green
gh workflow run "CI Pipeline" -f deploy_target=green

# Or automatic on push to main/master
git push origin main
```

### 3. **Deployment Process**
```
CI Pipeline → Build Image → Deploy to Green → Health Checks → Traffic Switch
     ↓             ↓             ↓             ↓             ↓
  Tests       Docker Hub    Green Env     Verify Health   Blue←→Green
Security     Push Image    Start App     Load Test       Update LB
```

### 4. **Traffic Switch**
- Load balancer routes 100% traffic to Green
- Blue environment kept running for rollback
- Monitor Green environment for issues

### 5. **Rollback (if needed)**
```bash
# Switch back to Blue
gh workflow run "CI Pipeline" -f deploy_target=blue
```

## ⚙️ Configuration

### Environment Variables

Set these in your GitHub repository secrets/variables:

```bash
# Docker Registry
DOCKER_USERNAME=your-dockerhub-username
DOCKER_PASSWORD=your-dockerhub-password

# Deployment URLs (per environment)
DEPLOY_URL=https://your-domain.com          # Active environment URL
HEALTH_CHECK_URL=https://your-domain.com/health/  # Health check endpoint
```

### GitHub Environments

Create these environments in your GitHub repository:

- `production-blue` - Blue production environment
- `production-green` - Green production environment
- `staging` - Staging environment

## 🔧 Infrastructure Requirements

### Load Balancer Configuration

Your load balancer must support routing to different backend environments:

#### Nginx Example
```nginx
upstream blue_backend {
    server blue-app-1:8000;
    server blue-app-2:8000;
}

upstream green_backend {
    server green-app-1:8000;
    server green-app-2:8000;
}

# Switch between blue and green by changing this variable
map $active_environment $backend {
    blue blue_backend;
    green green_backend;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://$backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### AWS ALB Example
- Create two target groups: `blue-targets`, `green-targets`
- Create ALB listener rule that routes based on host header
- Update target groups when switching environments

### Database Considerations

- **Shared Database**: Both environments use the same database
- **Schema Migrations**: Run migrations before switching traffic
- **Data Consistency**: Ensure no breaking schema changes

### Redis Considerations

- **Shared Redis**: Both environments can share Redis instance
- **Cache Keys**: Use environment-specific cache key prefixes
- **Session Storage**: Configure session backend appropriately

## 🚦 Health Checks

The pipeline performs comprehensive health checks:

### Application Health
```bash
curl -f https://your-domain.com/health/
```

### Database Connectivity
- PostgreSQL connection verification
- Redis ping checks

### Load Testing (Optional)
- Basic load test after deployment
- Response time verification

## 📊 Monitoring & Alerts

### Success Criteria
- ✅ All health checks pass
- ✅ Response time < 500ms
- ✅ Error rate < 1%
- ✅ Database connections healthy

### Rollback Triggers
- ❌ Health checks fail
- ❌ Error rate > 5%
- ❌ Response time > 2000ms
- ❌ Manual rollback request

## 🔄 Rollback Procedure

### Automatic Rollback
```bash
# Pipeline automatically rolls back on health check failure
# Traffic switches back to previous environment
```

### Manual Rollback
```bash
# Switch to Blue environment
gh workflow run "CI Pipeline" -f deploy_target=blue

# Switch to Green environment
gh workflow run "CI Pipeline" -f deploy_target=green
```

### Emergency Rollback
```bash
# Direct infrastructure rollback
cd infrastructure
./deploy.sh rollback
```

## 📈 Benefits

### ✅ Zero-Downtime Deployments
- Traffic switches instantly between environments
- No service interruption during deployment

### ✅ Instant Rollback
- Previous environment always available
- Rollback in seconds, not minutes

### ✅ Risk Reduction
- Test new deployment before going live
- Validate health before switching traffic

### ✅ A/B Testing Ready
- Can route percentage of traffic to new version
- Compare performance between versions

## 🛠️ Usage Examples

### Deploy to Green Environment
```bash
gh workflow run "CI Pipeline" -f deploy_target=green
```

### Deploy to Staging
```bash
gh workflow run "CI Pipeline" -f deploy_target=staging
```

### Force Deploy (skip tests)
```bash
gh workflow run "CI Pipeline" -f deploy_target=green -f force_deploy=true
```

### Check Deployment Status
```bash
# Check GitHub Actions
gh run list --workflow="CI Pipeline"

# Check application health
curl https://your-domain.com/health/
```

## 🔒 Security Considerations

- **Environment Isolation**: Blue and Green should be in separate network segments
- **Secret Management**: Use different secrets per environment
- **Access Control**: Limit who can trigger deployments
- **Audit Logging**: Log all deployment and traffic switch events

## 📚 Troubleshooting

### Common Issues

1. **Health Check Failures**
   - Check application logs: `docker-compose logs web`
   - Verify database connectivity
   - Check Redis connection

2. **Traffic Not Switching**
   - Verify load balancer configuration
   - Check DNS propagation
   - Confirm environment variables

3. **Database Migration Issues**
   - Run migrations manually: `docker-compose exec web python manage.py migrate`
   - Check migration files for conflicts

4. **Cache Issues**
   - Clear Redis cache if needed
   - Verify cache key prefixes

## 🎯 Best Practices

1. **Test in Staging First**: Always deploy to staging before production
2. **Monitor After Switch**: Watch metrics for 15-30 minutes after traffic switch
3. **Gradual Rollout**: Consider canary deployments for high-risk changes
4. **Backup Before Deploy**: Database backup created automatically
5. **Document Changes**: Keep changelog of deployments
6. **Automate Everything**: Use infrastructure as code for environments

## 📖 Related Documentation

- [CI/CD Pipeline](../.github/workflows/ci-cd.yml)
- [Infrastructure Deployment](README.md)
- [Docker Optimization](build-docker.sh)
- [Environment Configuration](.env.example)
