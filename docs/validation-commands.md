# Validation Commands Guide

This document provides a comprehensive list of commands to validate the EVPN-VXLAN fabric.

## Table of Contents
- [Underlay Validation](#underlay-validation)
- [Overlay Validation](#overlay-validation)
- [MLAG Validation](#mlag-validation)
- [VXLAN Validation](#vxlan-validation)
- [VRF Validation](#vrf-validation)
- [Troubleshooting](#troubleshooting)

## Underlay Validation

### Check BGP IPv4 Unicast Neighbors

```bash
# On Spine
show bgp ipv4 unicast summary

# On Leaf
show bgp ipv4 unicast summary
```

Expected: All neighbors in `Established` state

### Verify Loopback Reachability

```bash
# From any leaf, ping spine loopbacks
ping 10.0.250.1
ping 10.0.250.2

# From spine, ping all leaf loopbacks
ping 10.0.250.11
ping 10.0.250.12
# ... etc
```

### Check BGP Routes

```bash
# View all BGP routes
show ip bgp

# View routes for specific prefix
show ip bgp 10.0.250.0/24

# View ECMP paths
show ip route 10.0.250.11
```

Expected: Multiple equal-cost paths via both spines

### Verify Interface Status

```bash
# Check all interfaces
show interfaces status

# Check specific interface
show interfaces ethernet 11
```

## Overlay Validation

### Check BGP EVPN Neighbors

```bash
# On Spine
show bgp evpn summary

# On Leaf
show bgp evpn summary
```

Expected: All EVPN neighbors in `Established` state

### View EVPN Routes

```bash
# Show all EVPN routes
show bgp evpn

# Show Type-2 routes (MAC/IP)
show bgp evpn route-type mac-ip

# Show Type-5 routes (IP Prefix)
show bgp evpn route-type ip-prefix ipv4

# Show routes for specific VNI
show bgp evpn vni 110040
show bgp evpn vni 100001
```

### Check Route Distinguishers and Route Targets

```bash
# View RD/RT configuration
show running-config | section bgp

# View imported routes
show bgp evpn route-type ip-prefix ipv4 | grep RT
```

## MLAG Validation

### Check MLAG Status

```bash
# Overall MLAG status
show mlag

# MLAG interfaces
show mlag interfaces

# MLAG config-sanity
show mlag config-sanity
```

Expected output:
- State: Active
- Negotiation status: Connected
- Peer-link status: Up

### Verify Dual-Active Detection

```bash
# Check dual-active detection status
show mlag detail | include dual

# Verify heartbeat
show mlag detail | include Heartbeat
```

### Check Port-Channel Status

```bash
# View all port-channels
show port-channel summary

# Detailed port-channel info
show interfaces port-channel 999
show interfaces port-channel 1
```

## VXLAN Validation

### Check VXLAN Interface

```bash
# VXLAN interface summary
show interface vxlan1

# Detailed VXLAN info
show vxlan config-sanity
```

### Verify VTEPs

```bash
# Show remote VTEPs
show vxlan vtep

# Show VXLAN VNI mapping
show vxlan vni

# Show flood VTEPs
show vxlan flood vtep
```

### Check VXLAN Address Table

```bash
# Show all MAC addresses learned via VXLAN
show vxlan address-table

# Show MAC addresses for specific VLAN
show mac address-table vlan 40

# Show MAC addresses for specific VNI
show vxlan address-table vni 110040
```

### Verify Overlay Learning

```bash
# Check if EVPN control plane is learning MACs
show bgp evpn route-type mac-ip

# Compare with local MAC table
show mac address-table dynamic
```

## VRF Validation

### Check VRF Configuration

```bash
# List all VRFs
show vrf

# VRF routing table
show ip route vrf gold

# VRF interfaces
show ip interface vrf gold brief
```

### Verify VRF BGP

```bash
# BGP summary for VRF
show bgp ipv4 unicast vrf gold summary

# BGP routes in VRF
show bgp ipv4 unicast vrf gold
```

### Test VRF Connectivity

```bash
# Ping from VRF
ping vrf gold 10.78.78.78

# Traceroute in VRF
traceroute vrf gold 10.78.78.78
```

### Check VNI to VRF Mapping

```bash
# Show VRF to VNI mapping
show vxlan vrf

# Show Type-5 routes for VRF
show bgp evpn route-type ip-prefix ipv4 vrf gold
```

## Troubleshooting

### General Health Checks

```bash
# System health
show version
show inventory
show environment all

# Check for errors
show logging
show interfaces counters errors
```

### BGP Troubleshooting

```bash
# BGP process status
show ip bgp summary

# BGP neighbor details
show ip bgp neighbors 10.0.250.1

# BGP update messages
show bgp evpn neighbors 10.0.250.1 advertised-routes
show bgp evpn neighbors 10.0.250.1 received-routes
```

### VXLAN Troubleshooting

```bash
# VXLAN counters
show interfaces vxlan1 counters

# VXLAN flood list
show vxlan flood vtep

# Check for VXLAN errors
show vxlan counters
```

### MLAG Troubleshooting

```bash
# MLAG detailed status
show mlag detail

# MLAG inconsistencies
show mlag config-sanity

# Port-channel LACP status
show lacp interface
show lacp neighbor
```

### Packet Capture

```bash
# Capture BGP packets
bash tcpdump -i et11 -n port 179

# Capture VXLAN packets
bash tcpdump -i et11 -n port 4789

# Capture on VXLAN interface
monitor session vxlan source vxlan1 both
```

## Useful Show Commands by Category

### Quick Status Commands
```bash
show ip interface brief
show bgp summary
show vxlan vtep
show mlag
```

### Detailed Analysis Commands
```bash
show tech-support
show running-config
show ip route detail
show bgp evpn detail
```

### Real-time Monitoring
```bash
watch 1 show bgp evpn summary
watch 1 show vxlan address-table
watch 1 show mlag
```

## Expected Normal Output Examples

### Healthy BGP EVPN Summary (Leaf)
```
Neighbor         V  AS           MsgRcvd   MsgSent  InQ OutQ  Up/Down State  PfxRcd PfxAcc
10.0.250.1       4  65000             50        48    0    0 00:24:30 Estab  10     10
10.0.250.2       4  65000             49        47    0    0 00:24:25 Estab  10     10
```

### Healthy MLAG Status
```
MLAG Status:
state                   : Active
negotiation status      : Connected
peer-link status        : Up
local-int status        : Up
system-id               : c0:01:ca:fe:ba:be
dual-primary detection  : Configured
```

### Healthy VXLAN Interface
```
Vxlan1 is up, line protocol is up (connected)
  Hardware is Vxlan
  Source interface is Loopback1 and is active with 10.0.255.11
  Replication/Flood Mode is headend with Flood List Source: EVPN
  Remote MAC learning via EVPN
```

## Tips

1. **Always check both spines and leafs** - Verify configurations are symmetric
2. **Use 'watch' command** for real-time monitoring during changes
3. **Check logs** if something doesn't work as expected
4. **Verify bidirectional** connectivity and routing
5. **Test failure scenarios** by shutting down interfaces/devices

---

For more information, refer to:
- [Arista EOS EVPN Documentation](https://www.arista.com/en/um-eos/eos-section-41-1-evpn)
- [Arista VXLAN Configuration Guide](https://www.arista.com/en/um-eos/eos-vxlan)
