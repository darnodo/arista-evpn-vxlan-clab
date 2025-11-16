#!/bin/bash
# Cleanup script for Arista EVPN-VXLAN lab

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "========================================="
echo " EVPN-VXLAN Lab Cleanup"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run with sudo"
    exit 1
fi

# Confirm cleanup
print_warning "This will destroy the lab and clean up all resources!"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    print_info "Cleanup cancelled."
    exit 0
fi

# Destroy the lab
print_info "Destroying ContainerLab topology..."
if containerlab destroy -t evpn-lab.clab.yml --cleanup 2>/dev/null; then
    print_info "Lab destroyed successfully"
else
    print_warning "Lab may not be running or already destroyed"
fi

# Clean up any remaining containers
print_info "Checking for remaining lab containers..."
containers=$(docker ps -a | grep "clab-arista-evpn-fabric" | awk '{print $1}' || true)
if [ -n "$containers" ]; then
    print_info "Removing remaining containers..."
    echo "$containers" | xargs docker rm -f
else
    print_info "No remaining containers found"
fi

# Clean up networks
print_info "Checking for lab networks..."
networks=$(docker network ls | grep "evpn-mgmt" | awk '{print $1}' || true)
if [ -n "$networks" ]; then
    print_info "Removing lab networks..."
    echo "$networks" | xargs docker network rm
else
    print_info "No lab networks found"
fi

# Clean up clab directory
print_info "Cleaning up clab directory..."
if [ -d "clab-arista-evpn-fabric" ]; then
    rm -rf clab-arista-evpn-fabric
    print_info "Removed clab directory"
fi

# Optional: Clean up docker system
read -p "Do you want to run docker system prune? (y/N): " prune
if [[ $prune =~ ^[Yy]$ ]]; then
    print_info "Running docker system prune..."
    docker system prune -f
fi

echo ""
print_info "Cleanup complete!"
echo ""
print_info "To redeploy the lab, run:"
print_info "  sudo ./scripts/deploy.sh deploy"
echo ""
