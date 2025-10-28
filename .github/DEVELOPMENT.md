# Development Workflow & CI/CD

## Branch Strategy

**`develop`** → Auto-deploys to staging
**`master`** → Manual deploy to production

---

## Complete CI/CD Flow

### Scenario 1: Push to `develop` Branch

```bash
git checkout develop
# Make changes
git commit -m "Add feature"
git push origin develop
```

**What happens:**

1. **CI Pipeline Runs** (`ci.yml`)
   - ✅ Quality checks (lint, mypy)
   - ✅ Unit tests
   - ✅ Integration tests
   - ✅ Build Docker image
   - ✅ Security scan

2. **Images Created & Pushed:**

   **GitHub Container Registry (GHCR):**
   - `ghcr.io/manishasaraf57-dot/backend_easy:develop`
   - `ghcr.io/manishasaraf57-dot/backend_easy:develop-abc1234` (with SHA)
   - `ghcr.io/manishasaraf57-dot/backend_easy:sha-abc1234` (immutable)
   - `ghcr.io/manishasaraf57-dot/backend_easy:test` (for CI tests)
   - ❌ NOT tagged as `:latest` (only master gets this)

   **Google Artifact Registry (GAR):**
   - `asia-south1-docker.pkg.dev/.../backend_easy:develop`
   - `asia-south1-docker.pkg.dev/.../backend_easy:develop-abc1234`
   - `asia-south1-docker.pkg.dev/.../backend_easy:sha-abc1234`

3. **Deployment:**
   - ✅ **Staging auto-updates** to `:develop` image
   - Service: `backendeasy-staging`
   - URL: https://backendeasy-staging-lela6xnh4q-el.a.run.app
   - ❌ Production NOT touched

4. **Test Your Changes:**
   ```bash
   curl https://backendeasy-staging-lela6xnh4q-el.a.run.app/health/
   # Or visit staging admin: /admin/
   ```

---

### Scenario 2: Push to `master` Branch

```bash
git checkout master
git merge develop
git push origin master
```

**What happens:**

1. **CI Pipeline Runs** (same as develop)
   - ✅ Quality checks
   - ✅ All tests
   - ✅ Build Docker image
   - ✅ Security scan

2. **Images Created & Pushed:**

   **GitHub Container Registry (GHCR):**
   - `ghcr.io/manishasaraf57-dot/backend_easy:master`
   - `ghcr.io/manishasaraf57-dot/backend_easy:master-xyz5678`
   - `ghcr.io/manishasaraf57-dot/backend_easy:sha-xyz5678`
   - `ghcr.io/manishasaraf57-dot/backend_easy:test`
   - ✅ **Tagged as `:latest`** (stable release marker)

   **Google Artifact Registry (GAR):**
   - `asia-south1-docker.pkg.dev/.../backend_easy:master`
   - `asia-south1-docker.pkg.dev/.../backend_easy:master-xyz5678`
   - `asia-south1-docker.pkg.dev/.../backend_easy:sha-xyz5678`

3. **Deployment:**
   - ❌ **Production NOT auto-deployed** (manual approval required)
   - ✅ Image ready and waiting in GAR
   - ⏳ You must manually deploy (see Scenario 3)

---

### Scenario 3: Manual Deploy to Production

**After master CI completes, deploy to production:**

```bash
# Option 1: GitHub UI
# 1. Go to: https://github.com/manishasaraf57-dot/backend_easy/actions
# 2. Click "Deploy to Production"
# 3. Click "Run workflow"
# 4. Enter image_tag: master-xyz5678 (or sha-xyz5678)
# 5. Enter confirm: DEPLOY
# 6. Click "Run workflow"

# Option 2: CLI
gh workflow run deploy-production.yml \
  --field image_tag=master-xyz5678 \
  --field confirm=DEPLOY
```

**What happens:**

1. **Deploy Workflow Runs** (`deploy-production.yml`)
   - ✅ Verifies image exists in GAR
   - ✅ Updates Cloud Run service `backendeasy`
   - ✅ Points to new image tag

2. **Production Updated:**
   - Service: `backendeasy`
   - URL: https://backendeasy-lela6xnh4q-el.a.run.app
   - Image: Uses the specific SHA you provided

3. **Verify Deployment:**
   ```bash
   curl https://backendeasy-lela6xnh4q-el.a.run.app/health/
   ```

---

## Image Tag Reference

### Tags Created on Every Push:

| Branch | GHCR Tags | GAR Tags | :latest tag? |
|--------|-----------|----------|--------------|
| `develop` | `develop`<br>`develop-SHA`<br>`sha-SHA`<br>`test` | `develop`<br>`develop-SHA`<br>`sha-SHA` | ❌ No |
| `master` | `master`<br>`master-SHA`<br>`sha-SHA`<br>`test`<br>**`:latest`** | `master`<br>`master-SHA`<br>`sha-SHA` | ✅ Yes |

### Which Tag to Use?

- **Staging:** Uses `:develop` (auto-updates on every develop push)
- **Production:** Uses `master-SHA` or `sha-SHA` (immutable, pinned version)
- **`:latest`:** Only for reference, not used in deployments

---

## Test Skip Logic

CI intelligently skips tests when:
1. **Only config files changed** (`.yml`, `.md`, `docker-compose`)
2. **AND previous tests passed**

If previous tests failed → tests ALWAYS run (even for config-only changes)

---

## Complete Flow Diagram

```
┌─────────────┐
│   develop   │
│   branch    │
└──────┬──────┘
       │ git push
       ▼
┌─────────────────────────────┐
│   CI Pipeline (develop)     │
│  - Tests run                │
│  - Build image              │
│  - Push to GHCR & GAR       │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Images in Registries       │
│  GHCR: :develop, :test      │
│  GAR:  :develop-SHA         │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Staging Auto-Deploy        │
│  backendeasy-staging        │
│  Uses :develop image        │
└─────────────────────────────┘


┌─────────────┐
│   master    │
│   branch    │
└──────┬──────┘
       │ git push
       ▼
┌─────────────────────────────┐
│   CI Pipeline (master)      │
│  - Tests run                │
│  - Build image              │
│  - Tag as :latest           │
│  - Push to GHCR & GAR       │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Images in Registries       │
│  GHCR: :master, :latest     │
│  GAR:  :master-SHA          │
└──────┬──────────────────────┘
       │
       │ MANUAL STEP
       ▼
┌─────────────────────────────┐
│  Manual Deploy Trigger      │
│  gh workflow run            │
│  image_tag=master-SHA       │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Production Deploy          │
│  backendeasy                │
│  Uses :master-SHA image     │
└─────────────────────────────┘
```

---

## Quick Reference

### Check Image in GAR:
```bash
gcloud artifacts docker tags list \
  asia-south1-docker.pkg.dev/project-283878a7-633d-4014-a7f/backend-repo/backend_easy
```

### Check Current Production Image:
```bash
gcloud run services describe backendeasy \
  --region=asia-south1 \
  --format="value(spec.template.spec.containers[0].image)"
```

### Check CI Status:
```bash
gh run list --branch develop --limit 5
gh run list --branch master --limit 5
```

### View Specific Run:
```bash
gh run view RUN_ID --log
```

---

## Summary

| Action | develop | master |
|--------|---------|--------|
| **CI runs?** | ✅ Yes | ✅ Yes |
| **Tests run?** | ✅ Yes (with smart skip) | ✅ Yes |
| **Images pushed?** | ✅ GHCR + GAR | ✅ GHCR + GAR |
| **`:latest` tag?** | ❌ No | ✅ Yes |
| **Staging deploys?** | ✅ Auto | ❌ No |
| **Production deploys?** | ❌ No | ⏳ Manual |

**Best Practice:**
- Develop on `develop` branch
- Test on staging
- Merge to `master` when ready
- Manually deploy to production
