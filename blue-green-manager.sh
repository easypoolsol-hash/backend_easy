#!/bin/bash
# Blue-Green Docker Tag Management Script
# Helps manage Docker tags for blue-green deployments on Docker Hub free tier

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
DOCKER_USERNAME=${DOCKER_USERNAME:-""}
IMAGE_NAME="bus_kiosk_backend"
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Docker login
check_docker() {
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    if [ -z "$DOCKER_USERNAME" ]; then
        log_error "DOCKER_USERNAME environment variable not set"
        echo "Please set: export DOCKER_USERNAME=your-dockerhub-username"
        exit 1
    fi
}

# Show current tags
show_tags() {
    log_info "Current tags in repository: ${FULL_IMAGE_NAME}"

    # Try to get tags from Docker Hub API
    if command -v curl &> /dev/null; then
        local token=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:${FULL_IMAGE_NAME}:pull" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
        if [ -n "$token" ]; then
            local tags=$(curl -s -H "Authorization: Bearer ${token}" "https://registry-1.docker.io/v2/${FULL_IMAGE_NAME}/tags/list" | grep -o '"tags":\[[^]]*\]' | grep -o '"[^"]*"' | tr -d '"')
            if [ -n "$tags" ]; then
                echo "Available tags:"
                echo "$tags" | tr ' ' '\n' | sort
                return
            fi
        fi
    fi

    log_warning "Could not fetch tags from Docker Hub API"
    log_info "Use 'docker pull ${FULL_IMAGE_NAME}:tag' to check specific tags"
}

# Promote image between environments
promote_image() {
    local from_tag=$1
    local to_tag=$2

    if [ -z "$from_tag" ] || [ -z "$to_tag" ]; then
        log_error "Usage: $0 promote <from_tag> <to_tag>"
        echo "Example: $0 promote latest blue"
        exit 1
    fi

    log_info "Promoting image from '${from_tag}' to '${to_tag}'"

    # Pull the source image
    log_info "Pulling source image: ${FULL_IMAGE_NAME}:${from_tag}"
    if ! docker pull "${FULL_IMAGE_NAME}:${from_tag}"; then
        log_error "Failed to pull source image"
        exit 1
    fi

    # Tag it with the target tag
    log_info "Tagging as: ${FULL_IMAGE_NAME}:${to_tag}"
    docker tag "${FULL_IMAGE_NAME}:${from_tag}" "${FULL_IMAGE_NAME}:${to_tag}"

    # Push the new tag
    log_info "Pushing to Docker Hub: ${FULL_IMAGE_NAME}:${to_tag}"
    if ! docker push "${FULL_IMAGE_NAME}:${to_tag}"; then
        log_error "Failed to push image"
        exit 1
    fi

    log_success "Successfully promoted ${from_tag} → ${to_tag}"
}

# Switch blue-green environments
switch_environment() {
    local target=$1

    if [ "$target" != "blue" ] && [ "$target" != "green" ]; then
        log_error "Target must be 'blue' or 'green'"
        exit 1
    fi

    local opposite="blue"
    if [ "$target" = "blue" ]; then
        opposite="green"
    fi

    log_info "Switching active environment to: ${target}"
    log_warning "This will make ${target} the active environment"
    log_warning "Keep ${opposite} running for rollback capability"

    # Here you would typically update your load balancer
    # For now, just show what would happen
    echo ""
    echo "🔄 Environment Switch Commands:"
    echo "   1. Update load balancer to route to ${target} environment"
    echo "   2. Verify ${target} environment health"
    echo "   3. Keep ${opposite} environment running for rollback"
    echo ""
    echo "📋 Manual Load Balancer Update:"
    echo "   # Nginx example:"
    echo "   sed -i 's/set \$active_environment \"${opposite}\"/set \$active_environment \"${target}\"/' /etc/nginx/nginx.conf"
    echo "   nginx -s reload"
    echo ""
    echo "   # Or update your infrastructure automation"
}

# Show status
show_status() {
    log_info "Blue-Green Deployment Status"
    echo ""

    # Check if images exist
    for tag in blue green staging latest; do
        if docker manifest inspect "${FULL_IMAGE_NAME}:${tag}" &> /dev/null; then
            echo -e "✅ ${tag}: Available"
        else
            echo -e "❌ ${tag}: Not found"
        fi
    done

    echo ""
    log_info "Repository: ${FULL_IMAGE_NAME}"
    log_info "Free Tier: Using single repository with multiple tags"
}

# Main function
main() {
    echo "🐳 Blue-Green Docker Tag Manager"
    echo "================================="
    echo "Repository: ${FULL_IMAGE_NAME}"
    echo "Free Tier: ✅ Compatible (single repo, multiple tags)"
    echo ""

    check_docker

    case "${1:-}" in
        "status"|"show")
            show_status
            ;;
        "tags"|"list")
            show_tags
            ;;
        "promote")
            promote_image "$2" "$3"
            ;;
        "switch")
            switch_environment "$2"
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  status     Show current blue-green status"
            echo "  tags       List all available tags"
            echo "  promote <from> <to>  Copy tag (e.g., promote latest blue)"
            echo "  switch <blue|green>  Switch active environment"
            echo "  help       Show this help"
            echo ""
            echo "Examples:"
            echo "  $0 status"
            echo "  $0 promote latest green"
            echo "  $0 switch blue"
            ;;
        *)
            log_error "Unknown command: $1"
            echo "Run '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
