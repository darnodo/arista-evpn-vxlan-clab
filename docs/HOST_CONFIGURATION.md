# Host Interface Configuration Summary

## Overview
This document describes the persistent interface configuration approach for hosts in the Arista EVPN-VXLAN lab.

## Configuration Method
Hosts use persistent `/etc/network/interfaces` files mounted via ContainerLab's `binds` feature. This ensures:
- Configuration persists across container restarts
- Clean deployments without manual post-configuration
- Proper LACP bonding with VLAN tagging on Alpine Linux hosts

## Host Configurations

### Host1 (VTEP1 - L2 VXLAN on VLAN 40)
- **Location**: configs/host1-interfaces
- **IP Address**: 10.40.40.101/24
- **VLAN**: 40 (tagged)
- **Bonding**: LACP (802.3ad) using eth1 and eth2
- **Connected to**: leaf1 (eth1) and leaf2 (eth1)

### Host2 (VTEP2 - L3 VXLAN in VRF gold on VLAN 34)
- **Location**: configs/host2-interfaces
- **IP Address**: 10.34.34.102/24
- **VLAN**: 34 (tagged)
- **Gateway**: 10.34.34.1
- **Bonding**: LACP (802.3ad) using eth1 and eth2
- **Connected to**: leaf3 (eth1) and leaf4 (eth1)

### Host3 (VTEP3 - L2 VXLAN on VLAN 40)
- **Location**: configs/host3-interfaces
- **IP Address**: 10.40.40.103/24
- **VLAN**: 40 (tagged)
- **Bonding**: LACP (802.3ad) using eth1 and eth2
- **Connected to**: leaf5 (eth1) and leaf6 (eth1)

### Host4 (VTEP4 - L3 VXLAN in VRF gold on VLAN 78)
- **Location**: configs/host4-interfaces
- **IP Address**: 10.78.78.104/24
- **VLAN**: 78 (tagged)
- **Gateway**: 10.78.78.1
- **Bonding**: LACP (802.3ad) using eth1 and eth2
- **Connected to**: leaf7 (eth1) and leaf8 (eth1)

## Interface File Structure
All host interface files follow this pattern:

```
auto lo
iface lo inet loopback

auto bond0
iface bond0 inet manual
    use bond
    bond-slaves eth1 eth2
    bond-mode 802.3ad
    bond-miimon 100
    bond-lacp-rate fast
    up ip link set $IFACE up

auto bond0.<vlan>
iface bond0.<vlan> inet static
    address <ip_address>
    netmask 255.255.255.0
    [gateway <gateway_ip>]  # Only for L3 VXLAN hosts
    vlan-raw-device bond0
    up ip link set $IFACE up
```

## Key Configuration Points

### Alpine Linux Bonding Syntax
- Uses `use bond` directive (specific to ifupdown-ng in Alpine Linux)
- LACP mode configured via `bond-mode 802.3ad`
- Fast LACP rate for quicker failover detection

### VLAN Tagging
- VLANs are tagged by the hosts using subinterfaces (bond0.40, bond0.34, bond0.78)
- Switch ports are configured in trunk mode, NOT access mode
- This prevents layer 2/3 mismatches that would break VXLAN connectivity

### Topology Integration
The topology file (evpn-lab.clab.yml) mounts these files using binds:
```yaml
host1:
    kind: linux
    image: alpine:latest
    binds:
        - configs/host1-interfaces:/etc/network/interfaces
```

## Testing Connectivity

### L2 VXLAN (VLAN 40)
Host1 and Host3 should be able to ping each other:
```bash
# From host1
ping 10.40.40.103

# From host3
ping 10.40.40.101
```

### L3 VXLAN (VRF gold)
Host2 and Host4 should be able to ping each other:
```bash
# From host2
ping 10.78.78.104

# From host4
ping 10.34.34.102
```

## Verification Commands

### On hosts - Check bonding status:
```bash
cat /proc/net/bonding/bond0
ip link show bond0
ip addr show bond0.<vlan>
```

### On leaf switches - Check MLAG port-channels:
```bash
show mlag interfaces
show port-channel summary
show interfaces status
```

### On leaf switches - Check VXLAN:
```bash
show vxlan vtep
show vxlan address-table
show bgp evpn route-type mac-ip
show bgp evpn route-type ip-prefix ipv4
```
