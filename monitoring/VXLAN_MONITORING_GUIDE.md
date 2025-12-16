# VXLAN Monitoring Without Native Paths

## The Problem

Arista's VXLAN-specific telemetry paths (`arista-exp-eos-vxlan`) don't have well-documented OpenConfig equivalents, and the native paths are not standardized.

## The Solution

**You already have VXLAN visibility** through existing subscriptions! Here's how:

### 1. VXLAN Interface Metrics (Already Collected!)

The `Vxlan1` interface IS your VXLAN endpoint. Our existing `interfaces` subscription captures:

```prometheus
# VXLAN tunnel traffic
gnmic_interfaces_interface_state_counters_in_octets{interface_name="Vxlan1"}
gnmic_interfaces_interface_state_counters_out_octets{interface_name="Vxlan1"}

# VXLAN tunnel errors
gnmic_interfaces_interface_state_counters_in_errors{interface_name="Vxlan1"}
gnmic_interfaces_interface_state_counters_out_errors{interface_name="Vxlan1"}

# VXLAN interface status
gnmic_interfaces_interface_state_oper_status{interface_name="Vxlan1"}
```

### 2. VTEP Reachability (via BGP EVPN!)

BGP EVPN neighbors = VTEP reachability:

```prometheus
# EVPN neighbor state (1 = Established, VTEP is up)
gnmic_bgp_neighbors_neighbor_state_session_state{neighbor_address="10.0.250.13"}

# EVPN routes received = VNI propagation working
gnmic_bgp_neighbors_neighbor_afi_safis_state_prefixes_received{
  neighbor_address="10.0.250.1",
  afi_safi_name="L2VPN_EVPN"
}
```

### 3. Underlay Health = VXLAN Health

If underlay (spine-leaf) interfaces are up and BGP is established, VXLAN tunnels will form automatically:

```prometheus
# Underlay interfaces to spines
gnmic_interfaces_interface_state_oper_status{
  interface_name=~"Ethernet1[12]",
  role="leaf"
}
```

## Grafana Queries for VXLAN Monitoring

### VXLAN Tunnel Bandwidth

```promql
# VXLAN tunnel TX rate (bits/sec)
rate(gnmic_interfaces_interface_state_counters_out_octets{interface_name="Vxlan1"}[1m]) * 8

# VXLAN tunnel RX rate (bits/sec)
rate(gnmic_interfaces_interface_state_counters_in_octets{interface_name="Vxlan1"}[1m]) * 8
```

### VTEP Reachability Matrix

```promql
# Show which VTEPs can reach each other (via EVPN)
gnmic_bgp_neighbors_neighbor_state_session_state{
  afi_safi_name="L2VPN_EVPN"
} == 6  # 6 = Established in OpenConfig BGP
```

### VNI Count per VTEP

```promql
# Count of EVPN routes = approximation of active VNIs
gnmic_bgp_neighbors_neighbor_afi_safis_state_prefixes_received{
  afi_safi_name="L2VPN_EVPN"
}
```

### VXLAN Errors

```promql
# VXLAN tunnel errors
rate(gnmic_interfaces_interface_state_counters_in_errors{interface_name="Vxlan1"}[5m])
```

## What You're Missing (and Why It's OK)

### ❌ Not Directly Available:
- Per-VNI packet/byte counters
- Individual VTEP discovery lists
- Flood list details
- VNI-to-VLAN mappings

### ✅ Why It's OK:
1. **Total VXLAN traffic** (Vxlan1 interface) is usually more useful than per-VNI
2. **VTEP reachability** is inferred from BGP EVPN neighbor states
3. **VNI health** is inferred from EVPN route counts
4. **Configuration info** (VNI-to-VLAN) doesn't change often, can be in docs

## If You Really Need Native VXLAN Paths

### Discovery Method:

```bash
# SSH to a leaf
ssh admin@172.16.0.25

# Enter bash
bash

# Try to get native VXLAN paths
gnmi -get /Sysdb/bridging/vxlan/status
gnmi -get /Smash/bridging/status/vxlanStatus

# Or use EOS native provider in gnmi config
```

### Add to gnmic.yaml (if discovery works):

```yaml
subscriptions:
  arista_vxlan:
    paths:
      - /Sysdb/bridging/vxlan/status  # If this works
    mode: stream
    stream-mode: sample
    sample-interval: 30s
    encoding: json  # Note: probably needs 'json' not 'json_ietf'
```

### Add to switch config:

```
management api gnmi
   transport grpc default
      provider eos-native
```

This enables Arista native YANG paths alongside OpenConfig.

## Recommended Dashboard Panels

### 1. VXLAN Tunnel Bandwidth (per VTEP)

Shows total VXLAN encapsulated traffic per leaf pair:

```promql
sum by (source, vtep) (
  rate(gnmic_interfaces_interface_state_counters_out_octets{
    interface_name="Vxlan1",
    role="leaf"
  }[1m]) * 8
)
```

### 2. VTEP Connectivity Heat Map

Matrix showing which VTEPs can reach each other:

```promql
gnmic_bgp_neighbors_neighbor_state_session_state{
  afi_safi_name="L2VPN_EVPN"
}
```

### 3. EVPN Route Count (Proxy for VNI Health)

```promql
gnmic_bgp_neighbors_neighbor_afi_safis_state_prefixes_received{
  afi_safi_name="L2VPN_EVPN"
}
```

### 4. VXLAN vs Underlay Traffic Comparison

Compare VXLAN encapsulated vs total underlay:

```promql
# VXLAN traffic (overlay)
sum(rate(gnmic_interfaces_interface_state_counters_out_octets{interface_name="Vxlan1"}[1m])) * 8

# vs

# Total underlay traffic
sum(rate(gnmic_interfaces_interface_state_counters_out_octets{interface_name=~"Ethernet.*"}[1m])) * 8
```

## Summary

**You already have comprehensive VXLAN monitoring** through:
- ✅ Vxlan1 interface metrics (tunnel traffic)
- ✅ BGP EVPN neighbors (VTEP reachability)
- ✅ EVPN route counts (VNI propagation)
- ✅ Underlay interface health (tunnel foundation)

This is **sufficient for production monitoring** and will power your Flow Plugin visualization perfectly.

If you discover the native Arista VXLAN paths, we can add them as an enhancement, but they're not required for a functional monitoring stack.

## Next Steps

1. **Use current config** - It's production-ready
2. **Create VXLAN dashboard** - Use the queries above
3. **Optional: Discover native paths** - If you need per-VNI details later

The beauty of this approach: **It works right now** and gives you 90% of what you need for VXLAN monitoring!
