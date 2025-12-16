#!/bin/bash
# Deploy monitoring stack for EVPN-VXLAN fabric
# This script starts gnmic, Prometheus, and Grafana

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================="
echo "EVPN Fabric Monitoring Stack"
echo "==================================="

# Check if ContainerLab management network exists
if ! docker network ls | grep -q "evpn-mgmt"; then
    echo "⚠️  Warning: ContainerLab management network 'evpn-mgmt' not found."
    echo "   Creating bridge network for monitoring..."
    docker network create evpn-mgmt 2>/dev/null || true
fi

# Start the stack
echo ""
echo "Starting monitoring services..."
docker-compose up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check service status
echo ""
echo "Service Status:"
echo "---------------"

if curl -s http://localhost:9804/metrics > /dev/null 2>&1; then
    echo "✅ gnmic:      http://localhost:9804/metrics"
else
    echo "❌ gnmic:      Not responding (check docker logs gnmic)"
fi

if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus: http://localhost:9090"
else
    echo "❌ Prometheus: Not responding"
fi

if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana:    http://localhost:3000 (admin/admin)"
else
    echo "❌ Grafana:    Not responding"
fi

echo ""
echo "==================================="
echo "Next Steps:"
echo "==================================="
echo "1. Open Grafana: http://localhost:3000"
echo "2. Login with admin/admin"
echo "3. Navigate to Dashboards > EVPN Fabric"
echo "4. To create a weathermap:"
echo "   - Create new panel"
echo "   - Select 'Network Weathermap' visualization"
echo "   - Add nodes and links manually"
echo ""
echo "To stop: docker-compose down"
echo "To view logs: docker-compose logs -f"
