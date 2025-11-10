# Unified CI/CD Pipeline

## **Simple Single-Flow Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    PUSH TO BRANCH                           │
│         (develop / staging / production)                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │  🎯 DETECT     │
            │  ENVIRONMENT   │
            └────────┬───────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
   ┌─────────┐             ┌──────────┐
   │ Quality │             │  Tests   │
   │ (lint + │◄───PARALLEL───►(matrix) │
   │  mypy)  │             │ u/i/c    │
   └────┬────┘             └────┬─────┘
        │                       │
        └───────────┬───────────┘
                    │
                    ▼
            ┌───────────────┐
            │  BUILD IMAGE  │
            │  (with cache) │
            └───────┬───────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
   ┌─────────┐           ┌──────────┐
   │Security │◄─PARALLEL─►│  Smoke   │
   │  Scan   │           │  Tests   │
   └────┬────┘           └────┬─────┘
        │                     │
        └──────────┬──────────┘
                   │
                   ▼
            ┌──────────┐
            │  DEPLOY  │
            │  TO ENV  │
            └──────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
     develop   staging   production
```

## **Active Workflow**

### ✅ `ci.yml` - Unified CI/CD Pipeline
**Trigger:** Push to `develop`, `staging`, or `production` branches

**What it does:**
1. 🎯 Detect which branch (auto-routes to environment)
2. ✅ Quality checks (lint + mypy) + 🧪 Tests (parallel matrix)
3. 🏗️ Build image (fresh every time, cached for speed)
4. 🔒 Security scan + 💨 Smoke tests (parallel)
5. 🚀 Deploy to correct environment (based on branch)

---

## Required GitHub Secrets

After `terraform apply`, set these 2 secrets:

```bash
# Get values from terraform
cd backend_easy_infra/terraform
terraform output

# Set in GitHub
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER \
  --body="<value from terraform output>"

gh secret set GCP_SERVICE_ACCOUNT \
  --body="github-actions@backend-easypool.iam.gserviceaccount.com"
```

Or via GitHub UI: **Settings → Secrets → Actions**

---

## How Deployment Works

```
1. Git push to main
   ↓
2. deploy.yml runs tests
   ↓ (tests pass)
3. Builds Docker image
   ↓
4. Pushes to GCP Artifact Registry
   ↓
5. [GitHub Actions STOPS]
   ↓
6. Cloud Run sees new image
   ↓
7. Auto-deploys to production
```

**No manual deployment commands!**
**Terraform configured Cloud Run to watch for new images.**

---

## What Each Workflow Does

### `deploy.yml` (Simple - Just Push Image)
- Tests → Build → Push
- GitHub Actions does **NOT** touch Cloud Run
- Cloud Run handles deployment automatically

### `ci.yml` (Full Testing - Optional)
- Comprehensive testing for PRs
- Runs on all branches
- Does NOT push images or deploy

### `railway-cd.yml` (DELETE THIS)
- Old Railway deployment
- Not needed for GCP

### `build-image.yml` (DELETE THIS)
- Replaced by deploy.yml
- Not needed anymore

---

## Files to Delete

```bash
# Old/unused workflows
rm .github/workflows/railway-cd.yml
rm .github/workflows/build-image.yml

# Old deployment action (GitHub doesn't deploy anymore)
rm -rf .github/actions/deploy-cloud-run/
```

---

## Cost

| Service | Cost |
|---------|------|
| GitHub Actions | FREE (2000 min/month) |
| Build time per push | ~5-10 minutes |
| **Monthly cost** | **$0** |

---

## Troubleshooting

### Authentication Error
```bash
# Check secrets are set
gh secret list

# Should see:
# GCP_WORKLOAD_IDENTITY_PROVIDER
# GCP_SERVICE_ACCOUNT
```

### Image Pushes But Cloud Run Doesn't Update
```bash
# Check Cloud Run configuration
gcloud run services describe easypool-backend --region asia-south1 | grep image

# Should point to :latest tag
```

### Tests Fail
```bash
# Run locally first
python -m pytest tests/unit/ -v
ruff check .
```

---

## What Terraform Already Did

✅ Created Cloud Run services
✅ Configured to use `:latest` tag
✅ Set up secrets from Secret Manager
✅ Configured database connection
✅ Set up Workload Identity for GitHub
✅ Configured auto-deployment

**GitHub just needs to push the image!**

---

## Summary

**OLD WAY (Complex - 514 lines):**
- Separate paths for develop/PR/master/tags
- Complex decision trees
- Test tag management
- Cache-based promotion flows
- Digest verification between environments
- Confusing conditional logic

**NEW WAY (Simple - 253 lines):**
- Single unified workflow for all branches
- Branch detection auto-routes to environment
- Fresh build every time (guaranteed correctness)
- Cache for speed (not correctness)
- No test tags needed
- Clear, linear flow

## **Key Benefits**

✅ **Single workflow** - One file for all environments
✅ **Branch-based routing** - Push to `develop`/`staging`/`production`
✅ **Same quality checks** - All branches get same validation
✅ **Fresh builds** - Built every time to ensure correctness
✅ **Fast rebuilds** - GitHub Actions cache makes it quick
✅ **Parallel execution** - Tests and scans run simultaneously
✅ **No test tags** - Simplified, no complex tagging logic
✅ **Easy to understand** - Clear flow, easy to debug

## **Branch → Environment Mapping**

| Branch | Environment | Image Tags |
|--------|-------------|------------|
| `develop` | `dev` | `dev`, `dev-<sha>` |
| `staging` | `staging` | `staging`, `staging-<sha>` |
| `production` | `production` | `production`, `production-<sha>`, `latest` |

**Keep it simple!** 🎯
