#!/usr/bin/env bash
# Artifact Registry Cleanup Script
# Deletes old Docker images while keeping recent SHA-tagged versions
# Usage: ./cleanup-registry.sh [--keep-count=7] [--dry-run]

set -euo pipefail

# Configuration
PROJECT_ID="easypool-backend"
REGION="asia-south1"
REPOSITORY="backend-repo"
IMAGE_NAME="backend_easy"
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}"
KEEP_COUNT=7
DRY_RUN=false

# Parse arguments
for arg in "$@"; do
  case $arg in
    --keep-count=*)
      KEEP_COUNT="${arg#*=}"
      ;;
    --dry-run)
      DRY_RUN=true
      ;;
    --help)
      echo "Usage: $0 [--keep-count=7] [--dry-run]"
      echo ""
      echo "Options:"
      echo "  --keep-count=N   Keep N most recent SHA tags per environment (default: 7)"
      echo "  --dry-run        Show what would be deleted without actually deleting"
      echo ""
      echo "This script removes:"
      echo "  - Old develop-* tags (obsolete workflow)"
      echo "  - Old dev-hotfix-* tags (obsolete workflow)"
      echo "  - Old dev-* SHA tags (keeping $KEEP_COUNT newest)"
      echo "  - Old staging-* SHA tags (keeping $KEEP_COUNT newest)"
      echo "  - Old production-* SHA tags (keeping $KEEP_COUNT newest)"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

echo "=== Artifact Registry Cleanup ==="
echo "Project: $PROJECT_ID"
echo "Repository: $REPOSITORY"
echo "Image: $IMAGE_NAME"
echo "Keep count: $KEEP_COUNT per environment"
echo "Dry run: $DRY_RUN"
echo ""

# Function to delete images
delete_images() {
  local description=$1
  local tags_file=$2

  if [ ! -f "$tags_file" ] || [ ! -s "$tags_file" ]; then
    echo "No images to delete for: $description"
    return
  fi

  local count=$(wc -l < "$tags_file")
  echo "Deleting $count images: $description"

  if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would delete:"
    cat "$tags_file"
    return
  fi

  while read -r tag; do
    [ -z "$tag" ] && continue
    echo "  Deleting: $tag"
    gcloud artifacts docker images delete "${IMAGE_URL}:${tag}" \
      --delete-tags \
      --quiet 2>&1 | grep -E "(done\.|ERROR)" || true
  done < "$tags_file"
}

# Create temp directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

echo "Step 1: Collecting image tags..."

# Get all tags
gcloud artifacts docker images list "$IMAGE_URL" \
  --include-tags \
  --sort-by=~create_time \
  --format="csv[no-heading](tags)" \
  | tr ',' '\n' > "$TEMP_DIR/all_tags.txt"

# Step 2: Find obsolete workflow tags
echo "Step 2: Finding obsolete workflow tags..."
grep -E "^develop-" "$TEMP_DIR/all_tags.txt" | grep -v "^$" > "$TEMP_DIR/develop_tags.txt" || true
grep -E "^dev-hotfix-" "$TEMP_DIR/all_tags.txt" | grep -v "^$" > "$TEMP_DIR/hotfix_tags.txt" || true

# Step 3: Find old SHA tags for each environment
echo "Step 3: Finding old SHA tags (keeping $KEEP_COUNT newest per environment)..."

for env in dev staging production; do
  grep -E "^${env}-[a-f0-9]{40}$" "$TEMP_DIR/all_tags.txt" \
    | tail -n +$((KEEP_COUNT + 1)) > "$TEMP_DIR/old_${env}_tags.txt" || true
done

# Step 4: Delete images
echo ""
echo "Step 4: Deleting images..."
delete_images "obsolete develop-* tags" "$TEMP_DIR/develop_tags.txt"
delete_images "obsolete dev-hotfix-* tags" "$TEMP_DIR/hotfix_tags.txt"
delete_images "old dev-* SHA tags" "$TEMP_DIR/old_dev_tags.txt"
delete_images "old staging-* SHA tags" "$TEMP_DIR/old_staging_tags.txt"
delete_images "old production-* SHA tags" "$TEMP_DIR/old_production_tags.txt"

echo ""
echo "=== Cleanup Summary ==="

# Count remaining images
REMAINING=$(gcloud artifacts docker images list "$IMAGE_URL" --include-tags --format="csv[no-heading](tags)" | wc -l)
echo "Remaining images: $REMAINING"

# Show current repository size
SIZE_MB=$(gcloud artifacts repositories list \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --format="value(sizeBytes)" \
  --filter="name:$REPOSITORY")
if [ -n "$SIZE_MB" ]; then
  # sizeBytes is actually in MB (not bytes, despite the name)
  SIZE_INT=$(echo "$SIZE_MB" | awk '{printf "%.0f", $1}')
  echo "Current size: ${SIZE_INT} MB"
fi
echo ""
echo "Note: Storage savings will appear after GCP's garbage collection runs (usually within 24 hours)"

echo ""
echo "Cleanup complete!"
