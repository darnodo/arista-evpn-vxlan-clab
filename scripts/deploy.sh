#!/bin/bash
# Deployment script for Arista EVPN-VXLAN ContainerLab

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check if running as root or with sudo
    if [ "$EUID" -ne 0 ]; then 
        print_error "Please run with sudo"
        exit 1
    fi
    
    # Check if containerlab is installed
    if ! command -v containerlab &> /dev/null; then
        print_error "ContainerLab is not installed. Please install it first."
        print_info "Visit: https://containerlab.dev/install/"
        exit 1
    fi
    
    # Check if docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Check if cEOS image exists
    if ! docker images | grep -q "ceos.*4.35.0"; then
        print_warning "cEOS 4.35.0 image not found."
        print_info "Please import the cEOS image first:"
        print_info "  docker import cEOS64-lab-4.35.0F.tar ceos:4.35.0"
        read -p "Do you want to continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    print_info "All prerequisites met!"
}

# Function to deploy the lab
deploy_lab() {
    print_info "Deploying Arista EVPN-VXLAN lab..."
    
    # Deploy with containerlab
    if containerlab deploy -t evpn-lab.clab.yml; then
        print_info "Lab deployed successfully!"
        echo ""
        print_info "Lab Details:"
        containerlab inspect -t evpn-lab.clab.yml
        echo ""
        print_info "Access devices using:"
        print_info "  ssh admin@<container-name>"
        print_info "  Default password: admin"
        echo ""
        print_info "Or use docker exec:"
        print_info "  docker exec -it clab-arista-evpn-fabric-leaf1 Cli"
    else
        print_error "Deployment failed!"
        exit 1
    fi
}

# Function to display status
show_status() {
    print_info "Lab Status:"
    containerlab inspect -t evpn-lab.clab.yml
}

# Function to destroy the lab
destroy_lab() {
    print_warning "This will destroy the entire lab!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Destroying lab..."
        containerlab destroy -t evpn-lab.clab.yml --cleanup
        print_info "Lab destroyed successfully!"
    else
        print_info "Destruction cancelled."
    fi
}

# Function to restart the lab
restart_lab() {
    print_info "Restarting lab..."
    destroy_lab
    if [[ $? -eq 0 ]]; then
        sleep 2
        deploy_lab
    fi
}

# Function to show device access info
show_access_info() {
    print_info "Device Access Information:"
    echo ""
    echo "SSH Access (password: admin):"
    echo "  Spines:"
    echo "    ssh admin@clab-arista-evpn-fabric-spine1"
    echo "    ssh admin@clab-arista-evpn-fabric-spine2"
    echo ""
    echo "  Leafs:"
    for i in {1..8}; do
        echo "    ssh admin@clab-arista-evpn-fabric-leaf$i"
    done
    echo ""
    echo "Docker Exec:"
    echo "  docker exec -it clab-arista-evpn-fabric-<device-name> Cli"
    echo ""
    echo "Management IPs:"
    containerlab inspect -t evpn-lab.clab.yml | grep -E "spine|leaf" | awk '{print $2, $6}'
}

# Function to run basic validation
validate_lab() {
    print_info "Running basic validation..."
    
    # Check if containers are running
    if ! docker ps | grep -q "clab-arista-evpn-fabric"; then
        print_error "No lab containers found. Deploy the lab first."
        exit 1
    fi
    
    print_info "Checking BGP EVPN status on spine1..."
    docker exec clab-arista-evpn-fabric-spine1 Cli -p 15 -c "show bgp evpn summary"
    
    print_info "Checking VXLAN status on leaf1..."
    docker exec clab-arista-evpn-fabric-leaf1 Cli -p 15 -c "show vxlan vtep"
    
    print_info "Checking MLAG status on leaf1..."
    docker exec clab-arista-evpn-fabric-leaf1 Cli -p 15 -c "show mlag"
    
    print_info "Validation complete! Check output above for any issues."
}

# Main menu
show_menu() {
    echo ""
    echo "========================================="
    echo " Arista EVPN-VXLAN Lab Manager"
    echo "========================================="
    echo "1. Deploy Lab"
    echo "2. Show Status"
    echo "3. Destroy Lab"
    echo "4. Restart Lab"
    echo "5. Show Access Info"
    echo "6. Validate Lab"
    echo "7. Exit"
    echo "========================================="
}

# Main script
main() {
    # Check prerequisites first
    check_prerequisites
    
    # If arguments provided, execute directly
    if [ $# -gt 0 ]; then
        case "$1" in
            deploy)
                deploy_lab
                ;;
            status)
                show_status
                ;;
            destroy)
                destroy_lab
                ;;
            restart)
                restart_lab
                ;;
            access)
                show_access_info
                ;;
            validate)
                validate_lab
                ;;
            *)
                print_error "Unknown command: $1"
                echo "Usage: $0 {deploy|status|destroy|restart|access|validate}"
                exit 1
                ;;
        esac
        exit 0
    fi
    
    # Interactive menu
    while true; do
        show_menu
        read -p "Select option [1-7]: " choice
        case $choice in
            1)
                deploy_lab
                ;;
            2)
                show_status
                ;;
            3)
                destroy_lab
                ;;
            4)
                restart_lab
                ;;
            5)
                show_access_info
                ;;
            6)
                validate_lab
                ;;
            7)
                print_info "Exiting..."
                exit 0
                ;;
            *)
                print_error "Invalid option. Please select 1-7."
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# Run main function
main "$@"
