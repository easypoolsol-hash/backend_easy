#!/bin/bash
# Continuous Deployment Pipeline for Bus Kiosk Backend
# Run this script on your production server to deploy the latest image

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_USERNAME=${DOCKER_USERNAME:-"your-dockerhub-username"}
IMAGE_NAME="${DOCKER_USERNAME}/bus_kiosk_backend"
IMAGE_TAG=${IMAGE_TAG:-"latest"}
DEPLOY_ENV=${DEPLOY_ENV:-"production"}
TRAFFIC_PERCENTAGE=${TRAFFIC_PERCENTAGE:-100}
CANARY_MODE=${CANARY_MODE:-false}
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="bus_kiosk"

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available"
        exit 1
    fi

    # Check if .env file exists
    if [ ! -f ".env" ]; then
        log_error ".env file not found. Please create it from .env.example"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Pull latest images
pull_images() {
    log_info "Pulling latest Docker images..."

    # Pull the application image
    if ! docker pull "${IMAGE_NAME}:latest"; then
        log_error "Failed to pull application image"
        exit 1
    fi

    # Pull other service images (they should be up to date, but let's ensure)
    docker pull postgres:15-alpine
    docker pull redis:7-alpine
    docker pull nginx:1.25-alpine

    log_success "All images pulled successfully"
}

# Backup current database (optional)
backup_database() {
    if [ "${SKIP_BACKUP:-false}" = "true" ]; then
        log_warning "Skipping database backup as requested"
        return
    fi

    log_info "Creating database backup..."

    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"

    if docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U "${DB_USER:-bus_kiosk_user}" -d "${DB_NAME:-bus_kiosk}" > "$BACKUP_FILE" 2>/dev/null; then
        log_success "Database backup created: $BACKUP_FILE"
        echo "Backup saved to: $INFRA_DIR/$BACKUP_FILE"
    else
        log_warning "Could not create database backup (container might not be running)"
    fi
}

# Stop current services gracefully
stop_services() {
    log_info "Stopping current services gracefully..."

    # Try graceful shutdown first
    if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
        docker-compose -f docker-compose.prod.yml stop
        log_success "Services stopped gracefully"
    else
        log_info "No running services to stop"
    fi
}

# Start new services
start_services() {
    log_info "Starting new services..."

    # Start services
    if ! docker-compose -f docker-compose.prod.yml up -d; then
        log_error "Failed to start services"
        exit 1
    fi

    log_success "Services started successfully"
}

# Health check
health_check() {
    log_info "Performing health checks..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log_info "Health check attempt $attempt/$max_attempts..."

        # Check if all services are running
        if ! docker-compose -f docker-compose.prod.yml ps | grep -q "Exit"; then
            # Check application health endpoint
            if curl -f -s "http://localhost/health/" > /dev/null 2>&1; then
                log_success "Health check passed!"
                return 0
            fi
        fi

        sleep 10
        ((attempt++))
    done

    log_error "Health check failed after $max_attempts attempts"
    log_error "Check service logs: docker-compose -f docker-compose.prod.yml logs"
    return 1
}

# Cleanup old images and containers
cleanup() {
    if [ "${SKIP_CLEANUP:-false}" = "true" ]; then
        log_warning "Skipping cleanup as requested"
        return
    fi

    log_info "Cleaning up old Docker resources..."

    # Remove unused containers
    docker container prune -f

    # Remove unused images (but keep recent ones)
    docker image prune -f

    # Remove unused volumes (be careful!)
    # docker volume prune -f

    log_success "Cleanup completed"
}

# Rollback function
rollback() {
    log_error "Deployment failed! Starting rollback..."

    # Stop failed services
    docker-compose -f docker-compose.prod.yml down

    # Try to restore previous deployment
    log_info "Attempting to restore previous deployment..."

    # This would need more sophisticated rollback logic
    # For now, just log the issue
    log_error "Manual intervention required for rollback"
    log_info "Check the backup files and previous image tags"
}

# Show deployment summary
show_summary() {
    log_success "🎉 Deployment completed successfully!"
    echo ""
    echo "📊 Deployment Summary:"
    echo "   Image: ${IMAGE_NAME}:latest"
    echo "   Services: $(docker-compose -f docker-compose.prod.yml ps --services | wc -l)"
    echo "   Health: http://your-domain.com/health/"
    echo ""
    echo "🔧 Management Commands:"
    echo "   View logs: docker-compose -f docker-compose.prod.yml logs -f"
    echo "   Stop services: docker-compose -f docker-compose.prod.yml down"
    echo "   Restart: docker-compose -f docker-compose.prod.yml restart"
    echo ""
    echo "📝 Next Steps:"
    echo "   1. Update your DNS/load balancer if needed"
    echo "   2. Monitor application logs and metrics"
    echo "   3. Test the application endpoints"
}

# Main deployment function
main() {
    log_info "🚀 Starting CD Pipeline for Bus Kiosk Backend"
    log_info "Image: ${IMAGE_NAME}:latest"
    echo ""

    # Change to infrastructure directory
    cd "$INFRA_DIR"

    # Run deployment steps
    check_prerequisites
    pull_images
    backup_database
    stop_services

    # Start services with error handling
    if start_services && health_check; then
        cleanup
        show_summary
        log_success "✅ CD Pipeline completed successfully!"
        exit 0
    else
        rollback
        log_error "❌ CD Pipeline failed!"
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    "check")
        check_prerequisites
        log_success "Prerequisites check passed"
        ;;
    "pull")
        check_prerequisites
        pull_images
        ;;
    "backup")
        backup_database
        ;;
    "stop")
        stop_services
        ;;
    "start")
        start_services
        ;;
    "health")
        health_check
        ;;
    "cleanup")
        cleanup
        ;;
    *)
        main
        ;;
esac
