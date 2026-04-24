# Host Interface Configuration Files

This directory contains network interface configuration files for Alpine Linux hosts in the ContainerLab topology.

## Files

### DC hosts

- `dc-server1_interfaces` - Configuration for dc-server1 (VLAN 40, IP 10.40.40.101)
- `dc-server2_interfaces` - Configuration for dc-server2 (VLAN 34, IP 10.34.34.102)
- `dc-server3_interfaces` - Configuration for dc-server3 (VLAN 40, IP 10.40.40.103)
- `dc-server4_interfaces` - Configuration for dc-server4 (VLAN 78, IP 10.78.78.104)

### Campus hosts

Campus hosts are **single-attached** to a Campus access switch (enterprise user endpoint
pattern — no LACP bond, no VLAN trunking on the host side). Each host sits in a single
access VLAN that maps to VRF `gold`.

- `campus-dc-server1_interfaces` - Configuration for campus-host1 (VLAN 60 VRF gold 10.60.60.101/24, GW 10.60.60.1)
- `campus-dc-server2_interfaces` - Configuration for campus-host2 (VLAN 70 VRF gold 10.60.70.102/24, GW 10.60.70.1)

## Usage

Each file is mounted to `/etc/network/interfaces` in its respective host container via ContainerLab's `binds` feature:

```yaml
dc-server1:
    kind: linux
    image: alpine:latest
    binds:
        - hosts/dc-server1_interfaces:/etc/network/interfaces
```

## Format

Files use Debian/Alpine ifupdown format.

### DC hosts (dual-homed via LACP to access switches)

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

### Campus hosts (single-attached, no bonding, no VLAN tagging)

```
auto lo
iface lo inet loopback

auto eth1
iface eth1 inet static
    address <ip-address>/<mask>
    gateway <gateway>
```

## Key Concepts

### DC: LACP Bonding
- DC hosts use **mode 4** (802.3ad LACP) bonding
- Dual-homed to MLAG leaf pairs — typical for DC servers that need NIC-level redundancy
- Requires matching LACP configuration on switches

### Campus: Single-attached user endpoints
- Campus hosts use a single `eth1` interface connected to an access port
- Redundancy is handled at the access-switch layer (the access switch is itself
  dual-homed via LACP to the leaf MLAG pair), not at the host
- This matches the realistic enterprise pattern for PCs, phones, printers, etc.

### VLAN Tagging
- DC hosts: VLAN tagging happens in the host via `bond0.<vlan_id>` sub-interfaces
  (e.g., bond0.40, bond0.34, bond0.78); switch ports are trunks
- Campus hosts: no tagging on the host; the access switch places untagged frames
  into `switchport access vlan <id>`

### IP Addressing
- Static IP configuration on the host interface (sub-interface for DC, `eth1` for Campus)
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
