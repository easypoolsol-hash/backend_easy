## Description
<!-- What changes does this PR make? -->

## Checklist
- [ ] Code works in develop branch
- [ ] Tests pass locally
- [ ] Deployed to staging and tested
- [ ] Ready for production

## Deploy Instructions
```bash
# After merge to master, deploy with:
gh workflow run deploy-production.yml \
  --field image_tag=sha-XXXXXX \
  --field confirm=DEPLOY
```
