# Host Interface Configuration Guide

## Overview

All four hosts in the lab use **persistent interface configuration files** mounted via ContainerLab's `binds` feature. This approach provides cleaner, more maintainable configuration compared to using `exec` commands.

## Architecture

### Dual-Homing with LACP Bonding

Each host is dual-homed to an MLAG pair of leaf switches:
- **host1**: dual-homed to leaf1 + leaf2 (VTEP1)
- **host2**: dual-homed to leaf3 + leaf4 (VTEP2)
- **host3**: dual-homed to leaf5 + leaf6 (VTEP3)
- **host4**: dual-homed to leaf7 + leaf8 (VTEP4)

### VLAN Configuration

Hosts handle VLAN tagging using sub-interfaces on the bond:

| Host | VLAN | IP Address | Purpose | VRF |
|------|------|------------|---------|-----|
| host1 | 40 | 10.40.40.101/24 | L2 VXLAN test | default |
| host2 | 34 | 10.34.34.102/24 | L3 VXLAN test | gold |
| host3 | 40 | 10.40.40.103/24 | L2 VXLAN test | default |
| host4 | 78 | 10.78.78.104/24 | L3 VXLAN test | gold |

## Interface Files Structure

Each host has a configuration file in `hosts/` directory:
- `hosts/host1_interfaces` → mounted to `/etc/network/interfaces` in host1
- `hosts/host2_interfaces` → mounted to `/etc/network/interfaces` in host2
- `hosts/host3_interfaces` → mounted to `/etc/network/interfaces` in host3
- `hosts/host4_interfaces` → mounted to `/etc/network/interfaces` in host4

## Interface Configuration Format

### Example: host1_interfaces

```
auto lo
iface lo inet loopback

# Bond interface with LACP (802.3ad)
auto bond0
iface bond0 inet manual
    bond-mode 4
    bond-miimon 100
    bond-lacp-rate 1
    bond-slaves eth1 eth2

# VLAN 40 on bond0
auto bond0.40
iface bond0.40 inet static
    address 10.40.40.101
    netmask 255.255.255.0
    vlan-raw-device bond0
```

### Key Parameters Explained

**Bond Configuration:**
- `bond-mode 4`: LACP (802.3ad) mode - requires LACP on switch side
- `bond-miimon 100`: Link monitoring interval (100ms)
- `bond-lacp-rate 1`: Fast LACP (1 second intervals)
- `bond-slaves eth1 eth2`: Physical interfaces in the bond

**VLAN Sub-interface:**
- `bond0.40`: VLAN interface notation (bond0.VLAN_ID)
- `vlan-raw-device bond0`: Parent interface for VLAN
- Static IP configuration with address/netmask

## Deployment Process

When ContainerLab starts a host:

1. **Mount interface file** via binds
2. **Install packages**: `apk add ifupdown bonding vlan`
3. **Load kernel modules**:
   - `modprobe bonding` - enables LACP bonding
   - `modprobe 8021q` - enables VLAN tagging
4. **Bring up interfaces**: `ifup -a` reads `/etc/network/interfaces`

## Switch Configuration Requirements

For proper LACP operation, leaf switches must have:

```
interface Port-Channel1
   description host-X
   switchport mode trunk
   switchport trunk allowed vlan <vlan-id>
   mlag 1
   port-channel lacp fallback timeout 5
   port-channel lacp fallback individual
   no shutdown

interface Ethernet1
   description host-X-link1
   channel-group 1 mode active
   lacp timer fast
   no shutdown
```

**Critical settings:**
- `port-channel lacp fallback`: Required for ContainerLab timing
- `lacp timer fast`: Matches host's fast LACP rate
- `no shutdown`: Must explicitly enable Port-Channel interface

## Advantages of This Approach

1. **Persistence**: Configuration survives container restarts
2. **Clarity**: Single file shows complete network config
3. **Maintainability**: Easy to modify VLAN assignments
4. **Production-like**: Mirrors real-world dual-homing scenarios
5. **Clean deployment**: No manual post-deployment fixes needed

## Testing Connectivity

### L2 VXLAN (same VLAN)
```bash
# host1 (VLAN 40) → host3 (VLAN 40)
docker exec clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.103
```

### L3 VXLAN (inter-VRF)
```bash
# host2 (VLAN 34, VRF gold) → host4 (VLAN 78, VRF gold)
docker exec clab-arista-evpn-fabric-host2 ping -c 4 10.78.78.104
```

## Troubleshooting

### Verify bond status on host
```bash
docker exec clab-arista-evpn-fabric-host1 cat /proc/net/bonding/bond0
```

### Check VLAN interface
```bash
docker exec clab-arista-evpn-fabric-host1 ip addr show bond0.40
```

### Verify LACP on switch
```bash
ssh admin@clab-arista-evpn-fabric-leaf1 "show port-channel 1 detailed"
```

## References

- Alpine Linux ifupdown-ng documentation
- Linux bonding documentation: `/usr/src/linux/Documentation/networking/bonding.txt`
- Arista MLAG configuration guide
- srl-labs/srl-evpn-mh-lab (reference implementation)
