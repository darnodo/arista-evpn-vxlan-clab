# Quick Start Guide - EVPN-VXLAN Monitoring Stack

## Prerequisites

1. **ContainerLab topology deployed** with management network named `evpn-mgmt`
2. **Docker and Docker Compose** installed
3. **gNMI enabled on all switches** (should already be configured)

## Deployment Steps

### 1. Deploy the Monitoring Stack

```bash
# Navigate to monitoring directory
cd monitoring

# Start all services
docker-compose up -d

# Verify all services are running
docker-compose ps

# Expected output:
# NAME         STATUS          PORTS
# gnmic       Up (healthy)    0.0.0.0:9804->9804/tcp
# prometheus  Up (healthy)    0.0.0.0:9090->9090/tcp
# grafana     Up (healthy)    0.0.0.0:3000->3000/tcp
```

### 2. Verify gnmic is Collecting Metrics

```bash
# Check gnmic logs
docker logs gnmic

# Should see successful subscription messages like:
# "starting connection to target 'spine1'"
# "target 'spine1' gNMI connection established"

# Check metrics endpoint
curl http://localhost:9804/metrics | grep gnmic_interfaces | head -5

# Should see interface metrics:
# gnmic_interfaces_interface_state_counters_in_octets{...} 12345
# gnmic_interfaces_interface_state_counters_out_octets{...} 67890
```

### 3. Verify Prometheus is Scraping

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'

# Should show gnmic target as "up":
# {
#   "job": "gnmic",
#   "health": "up"
# }

# Query a specific metric
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=gnmic_interfaces_interface_state_counters_out_octets{source="spine1"}' \
  | jq '.data.result[0]'
```

### 4. Access Grafana

1. **Open browser**: http://localhost:3000
2. **Login** (optional): admin/admin
   - Or use anonymous access (Viewer role)
3. **Navigate to dashboards**:
   - Dashboards → Browse
   - Select "EVPN-VXLAN Fabric Flow Topology"

### 5. Generate Traffic (Optional)

To see bandwidth visualization in action:

```bash
# From your lab directory (not monitoring/)
cd ..

# Generate traffic between clients
# (Assumes you have traffic generation scripts)
bash scripts/generate-traffic.sh
```

## Accessing the Stack

### Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin/admin or anonymous |
| Prometheus | http://localhost:9090 | None |
| gnmic metrics | http://localhost:9804/metrics | None |

### Available Dashboards

1. **EVPN-VXLAN Fabric Flow Topology** (`fabric-flow-topology.json`)
   - Interactive flowchart of fabric topology
   - Real-time bandwidth overlays on links
   - Spine and leaf interface graphs

2. **Fabric Overview** (`fabric-overview.json`)
   - General fabric statistics
   - Device health overview

## Troubleshooting

### Problem: gnmic not collecting data

**Check switch gNMI configuration:**
```bash
# SSH to any switch
ssh admin@172.16.0.1

# Verify gNMI is enabled
show management api gnmi

# Should show:
# Enabled: yes
# Transport: GRPC
```

**If not enabled, add to switch configs:**
```
management api gnmi
   transport grpc default
```

### Problem: Prometheus shows no data

**Check:**
```bash
# 1. Verify gnmic is exposing metrics
curl http://localhost:9804/metrics | grep gnmic

# 2. Check Prometheus logs
docker logs prometheus | tail -20

# 3. Check Prometheus config is valid
docker exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

### Problem: Grafana dashboard shows "No Data"

**Check:**
1. **Prometheus datasource**: Configuration → Data Sources → Prometheus
   - URL should be: http://prometheus:9090
   - Click "Save & Test" - should show green "Data source is working"

2. **Query in Explore**:
   - Menu → Explore
   - Select "Prometheus" datasource
   - Run query: `gnmic_interfaces_interface_state_counters_out_octets`
   - Should return results

3. **Time range**: Ensure dashboard time range shows recent data (last 1h)

### Problem: Flow diagram not rendering

**Check:**
1. **Plugin installed**:
   ```bash
   docker exec grafana grafana-cli plugins ls | grep agenty
   ```
   Should show: agenty-flowcharting-panel

2. **If missing, reinstall**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## Stopping the Stack

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

## Updating Configuration

### Update gnmic subscriptions

1. Edit `gnmic/gnmic.yaml`
2. Restart gnmic:
   ```bash
   docker-compose restart gnmic
   ```

### Update Prometheus scrape config

1. Edit `prometheus/prometheus.yml`
2. Reload Prometheus (no restart needed):
   ```bash
   curl -X POST http://localhost:9090/-/reload
   ```

### Update Grafana dashboards

1. Edit JSON files in `grafana/dashboards/`
2. Restart Grafana:
   ```bash
   docker-compose restart grafana
   ```
   OR update via UI and export

## Next Steps

1. **Explore metrics**: Use Prometheus Explore to see all available metrics
2. **Create custom dashboards**: Build specific views for your use cases
3. **Add alerting**: Configure Prometheus alerting rules
4. **Add more visualizations**: Enhanced BGP, VXLAN, and MLAG dashboards

## Useful Commands

```bash
# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f gnmic

# Restart specific service
docker-compose restart prometheus

# Check resource usage
docker stats gnmic prometheus grafana

# Execute command in container
docker exec -it gnmic sh
```

## Support

- **gnmic**: https://gnmic.openconfig.net
- **Prometheus**: https://prometheus.io/docs
- **Grafana**: https://grafana.com/docs
- **Flow Plugin**: https://grafana.com/grafana/plugins/agenty-flowcharting-panel/

For issues specific to this lab, check the main repository documentation.
