# Arista EVPN-VXLAN ContainerLab

A production-ready Arista BGP EVPN-VXLAN data center fabric topology using ContainerLab and cEOS.

## 🎯 Overview

This lab demonstrates a complete EVPN-VXLAN data center fabric with:

- **2 Spine switches** (BGP Route Reflectors)
- **8 Leaf switches** forming 4 VTEPs (MLAG pairs)
- **BGP EVPN overlay** with L2/L3 VXLAN
- **MLAG configuration** for high availability
- **Test hosts** for validation

## 📐 Topology

```
                    ┌──────────┐  ┌──────────┐
                    │ Spine1  │  │ Spine2  │
                    │ AS65000 │  │ AS65000 │
                    └────┬────┘  └────┬────┘
                         │            │
         ┌───────────────┼────────────┼───────────────┐
         │               │            │               │
    ┌────┴────┐     ┌────┴────┐ ┌────┴────┐     ┌────┴────┐
    │ Leaf1/2 │     │ Leaf3/4 │ │ Leaf5/6 │     │ Leaf7/8 │
    │ AS65001 │     │ AS65002 │ │ AS65003 │     │ AS65004 │
    │  VTEP1  │     │  VTEP2  │ │  VTEP3  │     │  VTEP4  │
    └────┬────┘     └────┬────┘ └────┬────┘     └────┬────┘
         │               │            │               │
      Host1           Host2        Host3           Host4
```

## 🚀 Quick Start

### Prerequisites

- ContainerLab installed
- Docker installed
- Arista cEOS image: `ceos:4.35.0`

### Deploy the Lab

```bash
# Clone the repository
git clone https://gitea.arnodo.fr/Damien/arista-evpn-vxlan-clab.git
cd arista-evpn-vxlan-clab

# Deploy the topology
sudo containerlab deploy -t evpn-lab.clab.yml

# Check status
sudo containerlab inspect -t evpn-lab.clab.yml
```

### Access Devices

```bash
# SSH to any device (password: admin)
ssh admin@clab-arista-evpn-fabric-leaf1

# Or use docker exec
docker exec -it clab-arista-evpn-fabric-leaf1 Cli
```

## 📋 Configuration Details

### AS Numbers

- **Spine**: AS 65000
- **VTEP1 (Leaf1/2)**: AS 65001
- **VTEP2 (Leaf3/4)**: AS 65002
- **VTEP3 (Leaf5/6)**: AS 65003
- **VTEP4 (Leaf7/8)**: AS 65004

### IP Addressing

#### Management Network

- Subnet: `172.16.0.0/24`
- Spine1: `172.16.0.1`
- Spine2: `172.16.0.2`
- Leaf1-8: `172.16.0.25-32`

#### Loopback Interfaces

- **Router-ID Loopbacks (Lo0)**: `10.0.250.0/24`
    - Spine1: `10.0.250.1/32`
    - Spine2: `10.0.250.2/32`
    - Leaf1-8: `10.0.250.11-18/32`

- **VTEP Loopbacks (Lo1)**: `10.0.255.0/24`
    - VTEP1: `10.0.255.11/32`
    - VTEP2: `10.0.255.12/32`
    - VTEP3: `10.0.255.13/32`
    - VTEP4: `10.0.255.14/32`

#### Underlay P2P Links

- Spine1 to Leafs: `10.0.1.0/31`, `10.0.1.2/31`, ... `10.0.1.14/31`
- Spine2 to Leafs: `10.0.2.0/31`, `10.0.2.2/31`, ... `10.0.2.14/31`
- MLAG iBGP peering: `10.0.3.0/31`, `10.0.3.2/31`, `10.0.3.4/31`, `10.0.3.6/31`

#### Host Network Addressing

| Host  | VLAN | VRF     | IP Address      | Gateway    | Type     |
| ----- | ---- | ------- | --------------- | ---------- | -------- |
| host1 | 40   | default | 10.40.40.101/24 | -          | L2 VXLAN |
| host2 | 34   | gold    | 10.34.34.102/24 | 10.34.34.1 | L3 VXLAN |
| host3 | 40   | default | 10.40.40.103/24 | -          | L2 VXLAN |
| host4 | 78   | gold    | 10.78.78.104/24 | 10.78.78.1 | L3 VXLAN |

**Notes:**

- Host1 and Host3 are in VLAN 40 (L2 VXLAN only) and can communicate at Layer 2
- Host2 and Host4 are in VRF "gold" with different subnets, communicating via EVPN Type-5 routes (L3 VXLAN)
- All hosts use LACP bonding (802.3ad) with dual-homing to MLAG leaf pairs

### VXLAN Network Identifiers (VNI)

#### L2 VNI (VLAN to VNI Mapping)

| VLAN | Description   | VNI    | VTEPs                           | Route Target | Route Distinguisher        |
| ---- | ------------- | ------ | ------------------------------- | ------------ | -------------------------- |
| 40   | test-l2-vxlan | 110040 | VTEP1, VTEP3 (Leaf1/2, Leaf5/6) | 40:110040    | 65001:110040, 65003:110040 |

**L2 VNI Details:**

- VLAN 40 is stretched across VTEP1 (Leaf1/2) and VTEP3 (Leaf5/6) for pure Layer 2 connectivity
- Hosts in VLAN 40 (host1 and host3) communicate at Layer 2 across the EVPN fabric
- EVPN Type-2 (MAC/IP) routes are used for MAC address learning and distribution

#### L3 VNI (VRF to VNI Mapping)

| VRF  | Description                     | VNI    | VTEPs                           | Route Target | VLANs  |
| ---- | ------------------------------- | ------ | ------------------------------- | ------------ | ------ |
| gold | L3 VRF for inter-subnet routing | 100001 | VTEP2, VTEP4 (Leaf3/4, Leaf7/8) | 1:100001     | 34, 78 |

**L3 VNI Details:**

- VRF "gold" uses VNI 100001 for Layer 3 VXLAN routing between different subnets
- VLAN 34 (10.34.34.0/24) on VTEP2 and VLAN 78 (10.78.78.0/24) on VTEP4 are both in VRF gold
- EVPN Type-5 (IP Prefix) routes are used for inter-subnet routing
- Each VTEP advertises its local subnets via EVPN, enabling routed connectivity between host2 and host4

#### VNI Summary

| VNI Type | VNI    | Purpose                       | EVPN Route Type    |
| -------- | ------ | ----------------------------- | ------------------ |
| L2 VNI   | 110040 | Layer 2 extension for VLAN 40 | Type-2 (MAC/IP)    |
| L3 VNI   | 100001 | Layer 3 routing for VRF gold  | Type-5 (IP Prefix) |

### Features Implemented

✅ **Underlay**

- BGP IPv4 Unicast
- ECMP with 4 paths
- eBGP between Spine-Leaf
- iBGP between MLAG pairs

✅ **Overlay**

- BGP EVPN address family
- VXLAN data plane
- EVPN Type-2 (MAC/IP routes)
- EVPN Type-5 (IP Prefix routes)

✅ **High Availability**

- MLAG dual-homing
- Dual-active detection
- Anycast VTEP gateway

## 🧪 Testing & Validation

### Verify BGP EVPN Neighbors

```bash
# On any spine
show bgp evpn summary

# On any leaf
show bgp evpn summary
```

### Verify VXLAN

```bash
# Check VXLAN interface
show interface vxlan1

# Check remote VTEPs
show vxlan vtep

# Check VXLAN address table
show vxlan address-table
```

### Verify MLAG

```bash
# Check MLAG status
show mlag

# Check MLAG interfaces
show mlag interfaces
```

### Test Connectivity

#### L2 VXLAN Testing (VLAN 40)

Test Layer 2 connectivity between host1 and host3 across the EVPN fabric:

```bash
# From host1 to host3 (same VLAN 40, different VTEPs)
docker exec -it clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.103

# Check host1 interface
docker exec -it clab-arista-evpn-fabric-host1 ip addr show bond0

# From host3 to host1
docker exec -it clab-arista-evpn-fabric-host3 ping -c 4 10.40.40.101
```

#### L3 VXLAN Testing (VRF gold)

Test Layer 3 connectivity between host2 and host4 in VRF "gold":

```bash
# From host2 to host4 (different subnets via EVPN Type-5)
docker exec -it clab-arista-evpn-fabric-host2 ping -c 4 10.78.78.104

# From host4 to host2
docker exec -it clab-arista-evpn-fabric-host4 ping -c 4 10.34.34.102

# Check routing table on hosts
docker exec -it clab-arista-evpn-fabric-host2 ip route
docker exec -it clab-arista-evpn-fabric-host4 ip route
```

#### Verify EVPN Routes on Switches

```bash
# Check EVPN Type-2 routes (MAC/IP) - for VLAN 40
ssh admin@clab-arista-evpn-fabric-leaf1
show bgp evpn route-type mac-ip

# Check EVPN Type-5 routes (IP Prefix) - for VRF gold
ssh admin@clab-arista-evpn-fabric-leaf3
show bgp evpn route-type ip-prefix ipv4

# Verify VXLAN learned MACs
show vxlan address-table

# Check MAC addresses learned via EVPN
show mac address-table
```

## 📁 Repository Structure

```
arista-evpn-vxlan-clab/
├── README.md                    # This file
├── TROUBLESHOOTING.md           # Troubleshooting guide
├── END_TO_END_TESTING.md        # Testing procedures
├── evpn-lab.clab.yml            # ContainerLab topology
├── configs/                     # Device configurations
│   ├── spine1.cfg
│   ├── spine2.cfg
│   ├── leaf1.cfg
│   ├── leaf2.cfg
│   ├── leaf3.cfg
│   ├── leaf4.cfg
│   ├── leaf5.cfg
│   ├── leaf6.cfg
│   ├── leaf7.cfg
│   └── leaf8.cfg
└── hosts/                       # Host interface configurations
    ├── README.md
    ├── host1_interfaces
    ├── host2_interfaces
    ├── host3_interfaces
    └── host4_interfaces
```

## 🗑️ Cleanup

```bash
# Destroy the lab
sudo containerlab destroy -t evpn-lab.clab.yml

# Remove all related containers and networks
sudo containerlab destroy -t evpn-lab.clab.yml --cleanup
```

## 📚 References

- [Original Configuration Guide](https://overlaid.net/2019/01/27/arista-bgp-evpn-configuration-example/)
- [Arista EOS Documentation](https://www.arista.com/en/support/product-documentation)
- [ContainerLab Documentation](https://containerlab.dev/)
- [RFC 7432 - BGP MPLS-Based Ethernet VPN](https://tools.ietf.org/html/rfc7432)
- [RFC 8365 - A Network Virtualization Overlay Solution Using EVPN](https://tools.ietf.org/html/rfc8365)
