# Development Workflow

## Branch Strategy

**`develop`** → Auto-deploys to staging
**`master`** → Manual deploy to production

## Development Cycle

1. **Work on develop**
   ```bash
   git checkout develop
   # Make changes, commit
   git push origin develop
   ```
   - CI builds image: `backend_easy:develop`
   - Auto-deploys to: `backendeasy-staging`
   - Test at: https://backendeasy-staging-lela6xnh4q-el.a.run.app

2. **Merge to master**
   ```bash
   git checkout master
   git merge develop
   git push origin master
   ```
   - CI builds image: `backend_easy:master-XXXXX`
   - Does NOT auto-deploy to production
   - Image ready for manual production deployment

3. **Deploy to production**
   ```bash
   # Option 1: Via GitHub Actions UI
   # Go to Actions → "Deploy to Production" → Run workflow

   # Option 2: Via CLI
   gh workflow run deploy-production.yml \
     --field image_tag=master-XXXXXX \
     --field confirm=DEPLOY
   ```

## Summary

- **develop push** → staging auto-updates
- **master push** → production needs manual deploy
- **CI always runs** tests + builds on both branches
