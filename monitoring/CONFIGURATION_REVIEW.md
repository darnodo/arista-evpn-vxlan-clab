# Configuration Review Summary

## Overview
This document summarizes the configuration review and enhancements made to the EVPN-VXLAN monitoring stack to support Flow Plugin visualization.

## Changes Made

### 1. **gnmic Configuration** (`monitoring/gnmic/gnmic.yaml`)

#### ✅ Improvements:
- **Added BGP/EVPN telemetry subscriptions**
  - BGP neighbor state monitoring
  - EVPN AFI/SAFI metrics
  - Critical for overlay health visibility

- **Added routing telemetry**
  - Static routes monitoring
  - IPv4 unicast AFT entries
  - Underlay health visibility

- **Enhanced VXLAN subscriptions**
  - VLAN member state
  - Connection point endpoints
  - On-change streaming for real-time updates

- **Added MLAG telemetry**
  - LACP interface state
  - LACP member state
  - Redundancy monitoring

- **Optimized sample intervals**
  - Interfaces: 10s (was 15s) for better granularity
  - BGP/EVPN: 30s for overlay health
  - System: 30s for resource monitoring
  - MLAG: 15s for redundancy tracking

- **Enhanced event processors**
  - Better metric name transformation
  - Interface name cleanup (Ethernet → eth)
  - Source label enrichment

#### 📊 Key Metrics Now Available:
```
# Interface metrics (for Flow Plugin)
gnmic_interfaces_interface_state_counters_in_octets
gnmic_interfaces_interface_state_counters_out_octets
gnmic_interfaces_interface_state_oper_status
gnmic_interfaces_interface_state_admin_status

# BGP/EVPN metrics (overlay health)
gnmic_network_instances_bgp_neighbors_neighbor_state_session_state
gnmic_network_instances_bgp_neighbors_neighbor_afi_safis_state_prefixes_received
gnmic_network_instances_bgp_neighbors_neighbor_afi_safis_state_prefixes_sent

# MLAG metrics (redundancy)
gnmic_lacp_interfaces_interface_state_system_priority
gnmic_lacp_interfaces_interface_members_member_state_activity

# System metrics
gnmic_system_state_hostname
gnmic_system_memory_state_physical
gnmic_system_cpus_cpu_state_total_utilization
```

### 2. **Prometheus Configuration** (`monitoring/prometheus/prometheus.yml`)

#### ✅ Improvements:
- **Enhanced metric relabeling**
  - Explicit keep rules for interface, BGP, MLAG, system, and VXLAN metrics
  - Drop rule for unneeded metrics to reduce storage
  - Better than original overly-restrictive regex

- **Added topology label extraction**
  - Extracts device_type (spine/leaf) from source label
  - Extracts device_number for aggregation
  - Enables better Grafana queries

- **Additional cluster label**
  - Added `cluster: evpn-vxlan-lab` for multi-cluster scenarios

#### 📈 Metric Filtering Logic:
```yaml
# KEEP these patterns:
- gnmic_interfaces_.*          # All interface metrics
- gnmic_.*bgp.*                # All BGP metrics  
- gnmic_.*lacp.*               # All LACP/MLAG metrics
- gnmic_system.*               # All system metrics
- gnmic_.*vxlan.*|gnmic_.*vlan.* # VXLAN/VLAN metrics

# DROP everything else matching gnmic_.*
```

### 3. **Docker Compose** (`monitoring/docker-compose.yml`)

#### ✅ Improvements:
- **Replaced archived weathermap plugin** with active alternatives
  - `agenty-flowcharting-panel` - Flow/flowchart visualization
  - `yesoreyeram-infinity-datasource` - Enhanced data sources

- **Enabled anonymous access** for easier demo/testing
  - Anonymous role: Viewer (read-only)
  - Still requires admin/admin for editing

- **Added health checks** for all services
  - gnmic: checks /metrics endpoint
  - prometheus: checks /-/healthy endpoint  
  - grafana: checks /api/health endpoint

### 4. **New Flow Topology Dashboard** (`monitoring/grafana/dashboards/fabric-flow-topology.json`)

#### 🎨 Features:
- **Mermaid-style flowchart** showing fabric topology
  - 2 Spines (AS 65000)
  - 8 Leaves in 4 VTEP pairs (AS 65001-65004)
  - MLAG peer-link visualization
  - All spine-to-leaf uplinks

- **Live bandwidth overlays** on links
  - Real-time rate calculations using Prometheus queries
  - Color-coded thresholds (green → yellow → orange → red)
  - Pattern matching for automatic metric association

- **Separate bandwidth graphs**
  - Spine interface bandwidth (TX/RX)
  - Leaf interface bandwidth (TX/RX)
  - Mean and max calculations in legend

## Testing the Changes

### 1. Validate gnmic Configuration
```bash
# Test from gnmic container or locally with gnmic installed
gnmic -a 172.16.0.1:6030 -u admin -p admin --insecure capabilities

# Test specific subscription
gnmic -a 172.16.0.1:6030 -u admin -p admin --insecure \
  subscribe --path /network-instances/network-instance/protocols/protocol/bgp/neighbors \
  --stream-mode sample --sample-interval 10s
```

### 2. Check Prometheus Metrics
```bash
# Once stack is running
curl http://localhost:9804/metrics | grep gnmic_interfaces

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Query specific metric
curl -G http://localhost:9090/api/v1/query \
  --data-urlencode 'query=gnmic_interfaces_interface_state_counters_out_octets'
```

### 3. Verify Grafana Dashboards
1. Access http://localhost:3000
2. Navigate to Dashboards → EVPN-VXLAN Fabric Flow Topology
3. Verify:
   - Flow diagram renders correctly
   - Bandwidth overlays show on links
   - Time series graphs display data
   - Colors change based on utilization thresholds

## Comparison: Old vs New

### Old Configuration (weathermap)
- ❌ Used archived weathermap plugin (no longer maintained)
- ❌ Limited telemetry (interfaces only)
- ❌ No BGP/EVPN visibility
- ❌ Static bandwidth thresholds
- ❌ Manual metric path specification

### New Configuration (Flow Plugin)
- ✅ Uses actively maintained Flow Charting plugin
- ✅ Comprehensive telemetry (interfaces, BGP, EVPN, MLAG, system)
- ✅ Full overlay health visibility
- ✅ Dynamic bandwidth visualization
- ✅ Pattern-based automatic metric mapping
- ✅ Better metric organization and filtering

## Next Steps

### Recommended Additional Enhancements

1. **Add BGP State Dashboard**
   - BGP neighbor states across fabric
   - EVPN route counts per VTEP
   - Session flap detection

2. **Add VXLAN Overlay Dashboard**
   - Active VNIs per VTEP
   - VTEP reachability matrix
   - L2/L3 VXLAN traffic stats

3. **Add MLAG Health Dashboard**
   - Peer-link status and bandwidth
   - MLAG port status
   - Dual-active detection events

4. **Add Alerting Rules**
   - BGP session down alerts
   - Interface utilization thresholds
   - MLAG peer-link failures

5. **Add Recording Rules** (optional, for performance)
   ```yaml
   # Example: Pre-calculate interface utilization percentages
   - record: interface:bandwidth:utilization_percent
     expr: |
       (rate(gnmic_interfaces_interface_state_counters_out_octets[5m]) * 8 / 10000000000) * 100
   ```

## Troubleshooting

### Issue: No metrics in Prometheus
**Check:**
```bash
# Verify gnmic is collecting
docker logs gnmic

# Check gnmic metrics endpoint
curl http://localhost:9804/metrics

# Verify Prometheus can scrape
docker logs prometheus | grep gnmic
```

### Issue: Flow diagram not rendering
**Check:**
1. Flow Charting plugin installed: Settings → Plugins → search "agenty"
2. Prometheus datasource configured: Configuration → Data Sources
3. Metric queries returning data in Explore view
4. Browser console for JavaScript errors

### Issue: Missing BGP metrics
**Check:**
```bash
# SSH to a switch
ssh admin@172.16.0.1

# Verify gNMI is enabled
show management api gnmi
```

If not enabled on switches, add to configs:
```
management api gnmi
   transport grpc default
```

## References

- [gnmic Documentation](https://gnmic.openconfig.net)
- [Agenty Flow Charting Plugin](https://grafana.com/grafana/plugins/agenty-flowcharting-panel/)
- [Nokia SRL Telemetry Lab](https://github.com/srl-labs/srl-telemetry-lab) (reference implementation)
- [Arista gNMI Documentation](https://aristanetworks.github.io/openmgmt/)

## Summary

This configuration review has transformed your monitoring stack from using an archived plugin with limited visibility to a modern, comprehensive telemetry solution:

- **Better Plugin**: Active Flow Charting vs archived weathermap
- **More Data**: 5 subscription types vs 2 (interfaces, system, BGP, VXLAN, MLAG)
- **Better Filtering**: Explicit metric keeping vs overly restrictive regex
- **Health Checks**: Automated service health monitoring
- **Production Ready**: Comprehensive visibility of underlay AND overlay

The stack is now aligned with industry best practices as demonstrated in the Nokia SRL telemetry lab, adapted specifically for Arista cEOS switches.
