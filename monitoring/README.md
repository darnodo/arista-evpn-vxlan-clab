# Monitoring Stack Configuration
# gnmic -> Prometheus -> Grafana Network Weathermap
#
# This directory contains all configurations for monitoring
# the EVPN-VXLAN fabric using gNMI streaming telemetry

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ContainerLab Fabric                      │
│  ┌─────────┐ ┌─────────┐                                   │
│  │ spine1  │ │ spine2  │     gNMI port 6030                │
│  │ .0.1    │ │ .0.2    │                                   │
│  └────┬────┘ └────┬────┘                                   │
│       │           │                                         │
│  ┌────┴───┬───────┴────┬──────────┐                        │
│  │        │            │          │                         │
│  ▼        ▼            ▼          ▼                         │
│ leaf1-2  leaf3-4    leaf5-6    leaf7-8                     │
│ (VTEP1)  (VTEP2)    (VTEP3)    (VTEP4)                     │
└─────────────────────────────────────────────────────────────┘
       │ gNMI Streaming Telemetry (port 6030)
       ▼
┌─────────────────┐      ┌──────────────┐      ┌─────────────┐
│     gnmic       │─────▶│  Prometheus  │─────▶│   Grafana   │
│  (port 9804)    │      │  (port 9090) │      │ (port 3000) │
└─────────────────┘      └──────────────┘      └─────────────┘
```

## Quick Start

1. **Start the monitoring stack:**
   ```bash
   cd monitoring
   docker-compose up -d
   ```

2. **Access the dashboards:**
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090

3. **Verify gnmic targets:**
   ```bash
   curl -s http://localhost:9804/metrics | grep gnmic_target
   ```

## Components

| Component   | Port  | Description                           |
|-------------|-------|---------------------------------------|
| gnmic       | 9804  | gNMI collector with Prometheus output |
| Prometheus  | 9090  | Time-series database                  |
| Grafana     | 3000  | Visualization (weathermap + dashboards) |

## Device Management IPs

| Device  | Management IP  | gNMI Port | Role           |
|---------|----------------|-----------|----------------|
| spine1  | 172.16.0.1     | 6030      | Spine (AS65000)|
| spine2  | 172.16.0.2     | 6030      | Spine (AS65000)|
| leaf1   | 172.16.0.25    | 6030      | Leaf VTEP1     |
| leaf2   | 172.16.0.50    | 6030      | Leaf VTEP1     |
| leaf3   | 172.16.0.27    | 6030      | Leaf VTEP2     |
| leaf4   | 172.16.0.28    | 6030      | Leaf VTEP2     |
| leaf5   | 172.16.0.29    | 6030      | Leaf VTEP3     |
| leaf6   | 172.16.0.30    | 6030      | Leaf VTEP3     |
| leaf7   | 172.16.0.31    | 6030      | Leaf VTEP4     |
| leaf8   | 172.16.0.32    | 6030      | Leaf VTEP4     |

## Collected Metrics

### Interface Statistics
- In/Out octets, packets, errors
- Interface operational status
- Interface speed/duplex

### BGP State
- Neighbor state (Established, Active, etc.)
- Prefixes received/sent
- Session uptime

### EVPN/VXLAN
- VXLAN tunnel status
- VNI statistics
- EVPN route counts

## Grafana Weathermap

The weathermap visualization shows:
- Spine-leaf topology with live bandwidth colors
- Link utilization percentages
- BGP session states
- MLAG peer-link status

## Troubleshooting

**gnmic not connecting:**
```bash
# Test gNMI connectivity manually
gnmic -a 172.16.0.1:6030 -u admin -p admin --insecure capabilities
```

**No metrics in Prometheus:**
```bash
# Check gnmic logs
docker logs gnmic

# Verify Prometheus targets
curl http://localhost:9090/api/v1/targets
```
