# Manual Operations

This directory contains all manual operations that can be triggered via GitHub Actions.

## Architecture

```
.github/
├── workflows/
│   └── manual-operations.yml    # Single workflow orchestrator
└── operations/
    ├── migrate.sh               # Database migrations
    ├── seed-groups.sh          # Seed permission groups
    ├── seed-test-data.sh       # Seed test data
    ├── restart-service.sh      # Restart Cloud Run service
    ├── view-logs.sh            # View service logs
    ├── create-superuser.sh     # Create Django superuser
    ├── backup-database.sh      # Backup database
    └── clear-cache.sh          # Clear application cache
```

## How to Use

### Via GitHub UI

1. Go to **Actions** tab in GitHub
2. Select **"🎛️ Manual Operations"** workflow
3. Click **"Run workflow"** button
4. Fill in the form:
   - **Operation**: Choose what to run (migrate, seed-groups, etc.)
   - **Environment**: dev, staging, or production
   - **Dry Run**: Preview changes without applying
   - **Extra Args**: Optional additional arguments

### Via GitHub CLI

```bash
# Run migration on dev (dry run)
gh workflow run manual-operations.yml \
  -f operation=migrate \
  -f environment=dev \
  -f dry_run=true

# Seed groups on staging
gh workflow run manual-operations.yml \
  -f operation=seed-groups \
  -f environment=staging \
  -f dry_run=false

# View logs (last 100 entries)
gh workflow run manual-operations.yml \
  -f operation=view-logs \
  -f environment=production \
  -f extra_args=100
```

## Adding New Operations

1. Create a new script in `.github/operations/` (e.g., `my-operation.sh`)
2. Add the operation name to the dropdown in `manual-operations.yml`
3. Write your operation logic using these environment variables:
   - `$ENVIRONMENT` - Target environment (dev/staging/production)
   - `$DRY_RUN` - Whether this is a dry run (true/false)
   - `$EXTRA_ARGS` - Optional extra arguments
   - `$OPERATION` - The operation name

Example:

```bash
#!/bin/bash
# My Custom Operation

set -euo pipefail

echo "🚀 Running my operation on ${ENVIRONMENT}..."

if [ "$DRY_RUN" = "true" ]; then
  echo "🔍 DRY RUN - Would do something..."
else
  # Your actual operation here
  echo "✅ Operation complete!"
fi
```

## Benefits of This Architecture

### Before (Multiple Workflows)
❌ 10+ separate workflow files
❌ Hard to maintain
❌ Duplicated code
❌ Cluttered workflows directory

### After (Single Workflow + Operations)
✅ 1 workflow file
✅ Clean separation of concerns
✅ Easy to add new operations
✅ Organized and maintainable
✅ Reusable scripts
✅ Consistent interface

## Security

- All operations require environment approval (configured in GitHub)
- Production operations require manual approval
- Dry run mode available for safe testing
- All operations logged and auditable
