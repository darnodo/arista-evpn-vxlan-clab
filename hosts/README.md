# Host Interface Configuration Files

This directory contains network interface configuration files for Alpine Linux hosts in the ContainerLab topology.

## Files

### DC hosts

- `host1_interfaces` - Configuration for host1 (VLAN 40, IP 10.40.40.101)
- `host2_interfaces` - Configuration for host2 (VLAN 34, IP 10.34.34.102)
- `host3_interfaces` - Configuration for host3 (VLAN 40, IP 10.40.40.103)
- `host4_interfaces` - Configuration for host4 (VLAN 78, IP 10.78.78.104)

### Campus hosts

- `campus-host1_interfaces` - Configuration for campus-host1 (VLAN 50 stretched L2 10.50.50.101, VLAN 60 VRF gold 10.60.60.101)
- `campus-host2_interfaces` - Configuration for campus-host2 (VLAN 50 stretched L2 10.50.50.102, VLAN 70 VRF gold 10.60.70.102)

## Usage

Each file is mounted to `/etc/network/interfaces` in its respective host container via ContainerLab's `binds` feature:

```yaml
host1:
    kind: linux
    image: alpine:latest
    binds:
        - hosts/host1_interfaces:/etc/network/interfaces
```

## Format

Files use Debian/Alpine ifupdown format with bonding and VLAN extensions:

```
auto lo
iface lo inet loopback

auto bond0
iface bond0 inet manual
    bond-mode 4                 # LACP (802.3ad)
    bond-miimon 100
    bond-lacp-rate 1
    bond-slaves eth1 eth2

auto bond0.<vlan>
iface bond0.<vlan> inet static
    address <ip-address>
    netmask 255.255.255.0
    vlan-raw-device bond0
```

## Key Concepts

### LACP Bonding
- All hosts use **mode 4** (802.3ad LACP) bonding
- Dual-homed to MLAG leaf pairs for redundancy
- Requires matching LACP configuration on switches

### VLAN Tagging
- Hosts handle VLAN tagging via sub-interfaces
- Format: `bond0.<vlan_id>` (e.g., bond0.40, bond0.34, bond0.78)
- Switch ports are configured as trunks allowing specific VLANs

### IP Addressing
- Static IP configuration on VLAN sub-interfaces
- Subnet assignment based on VLAN ID pattern (e.g., VLAN 40 = 10.40.40.0/24)

## Modification

To change host configuration:

1. Edit the appropriate `host*_interfaces` file
2. Commit changes to git
3. Redeploy the lab: `sudo containerlab deploy -t evpn-lab.clab.yml --reconfigure`

No need to manually configure hosts after deployment - these files ensure clean, repeatable deployments.

## See Also

- [Main README](../README.md) - Project overview and quick start
- [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) - Troubleshooting guide
- [END_TO_END_TESTING.md](../END_TO_END_TESTING.md) - Testing procedures
