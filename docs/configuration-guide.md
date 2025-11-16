# Configuration Guide

This guide walks through the key configuration concepts used in this EVPN-VXLAN lab.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Underlay Configuration](#underlay-configuration)
- [Overlay Configuration](#overlay-configuration)
- [MLAG Configuration](#mlag-configuration)
- [L2 VXLAN Configuration](#l2-vxlan-configuration)
- [L3 VXLAN Configuration](#l3-vxlan-configuration)
- [Best Practices](#best-practices)

## Architecture Overview

### Topology Design
- **Spine-Leaf Architecture**: 2 Spines, 8 Leafs forming 4 VTEPs
- **Underlay**: BGP with eBGP between Spine-Leaf, iBGP between MLAG pairs
- **Overlay**: BGP EVPN for control plane
- **Data Plane**: VXLAN encapsulation

### AS Number Scheme
```
Spine:  AS 65000
VTEP1:  AS 65001 (Leaf1/Leaf2)
VTEP2:  AS 65002 (Leaf3/Leaf4)
VTEP3:  AS 65003 (Leaf5/Leaf6)
VTEP4:  AS 65004 (Leaf7/Leaf8)
```

### IP Addressing Plan
```
Management:           172.16.0.0/24
Router-ID Loopbacks:  10.0.250.0/24
VTEP Loopbacks:       10.0.255.0/24
Spine1 P2P Links:     10.0.1.0/24
Spine2 P2P Links:     10.0.2.0/24
MLAG iBGP Peering:    10.0.3.0/24
MLAG Peer-Link:       10.0.199.0/24
```

## Underlay Configuration

### 1. Enable Multi-Agent Routing Protocol Model

Required for EVPN to function properly:

```
service routing protocols model multi-agent
```

### 2. Configure Loopback Interfaces

Each device needs two loopbacks:

```
! Router-ID Loopback (unique per device)
interface Loopback0
   ip address 10.0.250.x/32

! VTEP Loopback (shared within MLAG pair)
interface Loopback1
   ip address 10.0.255.x/32
```

### 3. Configure Point-to-Point Interfaces

Use /31 subnets for efficiency:

```
interface Ethernet11
   description spine1
   no switchport
   ip address 10.0.1.1/31
   mtu 9214
```

### 4. Configure BGP Underlay

#### On Spines:
```
router bgp 65000
   router-id 10.0.250.1
   no bgp default ipv4-unicast
   distance bgp 20 200 200
   
   neighbor 10.0.1.1 remote-as 65001
   neighbor 10.0.1.3 remote-as 65001
   # ... more neighbors
   
   address-family ipv4
      neighbor 10.0.1.1 activate
      network 10.0.250.1/32
      maximum-paths 4 ecmp 64
```

#### On Leafs:
```
router bgp 65001
   router-id 10.0.250.11
   no bgp default ipv4-unicast
   distance bgp 20 200 200
   
   neighbor underlay peer group
   neighbor underlay remote-as 65000
   neighbor 10.0.1.0 peer group underlay
   neighbor 10.0.2.0 peer group underlay
   
   address-family ipv4
      neighbor underlay activate
      network 10.0.250.11/32
      network 10.0.255.11/32
      maximum-paths 4 ecmp 64
```

### Why These Settings?

- **no bgp default ipv4-unicast**: Requires explicit activation per address family
- **distance bgp 20 200 200**: eBGP=20, iBGP=200, Local=200 (prefer eBGP routes)
- **maximum-paths 4 ecmp 64**: Enable ECMP with up to 4 paths
- **mtu 9214**: Support jumbo frames for VXLAN overhead

## Overlay Configuration

### 1. Configure EVPN Neighbors

#### On Leafs:
```
router bgp 65001
   neighbor evpn peer group
   neighbor evpn remote-as 65000
   neighbor evpn update-source Loopback0
   neighbor evpn ebgp-multihop 3
   neighbor evpn send-community extended
   neighbor 10.0.250.1 peer group evpn
   neighbor 10.0.250.2 peer group evpn
   
   address-family evpn
      neighbor evpn activate
```

#### On Spines:
```
router bgp 65000
   neighbor evpn peer group
   neighbor evpn next-hop-unchanged
   neighbor evpn update-source Loopback0
   neighbor evpn ebgp-multihop 3
   neighbor evpn send-community extended
   
   neighbor 10.0.250.11 peer group evpn
   neighbor 10.0.250.11 remote-as 65001
   # ... more neighbors
   
   address-family evpn
      neighbor evpn activate
```

### Why These Settings?

- **update-source Loopback0**: Use loopback for stable peering
- **ebgp-multihop 3**: Allow multi-hop eBGP through underlay
- **send-community extended**: Required for EVPN route-targets
- **next-hop-unchanged**: On spines, preserve original next-hop for optimal routing

### 2. Configure VXLAN Interface

```
interface Vxlan1
   vxlan source-interface Loopback1
   vxlan udp-port 4789
   vxlan learn-restrict any
```

- **source-interface Loopback1**: Use VTEP loopback as source
- **udp-port 4789**: Standard VXLAN port
- **learn-restrict any**: Use EVPN control plane only (no data plane learning)

## MLAG Configuration

### 1. Configure MLAG VLANs

```
vlan 4090
   name mlag-peer
   trunk group mlag-peer

vlan 4091
   name mlag-ibgp
   trunk group mlag-peer
```

### 2. Configure MLAG SVIs

```
interface Vlan4090
   description MLAG Peer-Link
   ip address 10.0.199.254/31
   no autostate

interface Vlan4091
   description MLAG iBGP Peering
   ip address 10.0.3.0/31
   mtu 9214
```

### 3. Configure Peer-Link

```
interface Ethernet10
   channel-group 999 mode active

interface Port-Channel999
   switchport mode trunk
   switchport trunk group mlag-peer
   spanning-tree link-type point-to-point
```

### 4. Configure MLAG Domain

```
mlag configuration
   domain-id leafs
   local-interface Vlan4090
   peer-address 10.0.199.255
   peer-link Port-Channel999
   dual-primary detection delay 10 action errdisable all-interfaces
   peer-address heartbeat 172.16.0.50 vrf mgmt
```

### 5. Configure iBGP Between MLAG Peers

```
router bgp 65001
   neighbor underlay_ibgp peer group
   neighbor underlay_ibgp remote-as 65001
   neighbor underlay_ibgp next-hop-self
   neighbor 10.0.3.1 peer group underlay_ibgp
   
   address-family ipv4
      neighbor underlay_ibgp activate
```

### 6. Configure Virtual Router MAC

```
ip virtual-router mac-address c001.cafe.babe
```

This MAC is used for anycast gateway functionality across the MLAG pair.

## L2 VXLAN Configuration

For extending Layer 2 domains across the fabric:

### 1. Create VLAN

```
vlan 40
   name test-l2-vxlan
```

### 2. Map VLAN to VNI

```
interface Vxlan1
   vxlan vlan 40 vni 110040
```

### 3. Configure BGP EVPN for VLAN

```
router bgp 65001
   vlan 40
      rd 65001:110040
      route-target both 40:110040
      redistribute learned
```

### Key Concepts

- **VNI (VXLAN Network Identifier)**: 24-bit segment ID (110040)
- **RD (Route Distinguisher)**: Makes routes unique (AS:VNI format)
- **RT (Route Target)**: Controls route import/export (VLAN:VNI format)
- **redistribute learned**: Advertise locally learned MAC addresses

## L3 VXLAN Configuration

For routing between VRFs across the fabric:

### 1. Create VRF

```
vrf instance gold

ip routing vrf gold
```

### 2. Map VRF to VNI

```
interface Vxlan1
   vxlan vrf gold vni 100001
```

### 3. Configure VRF VLAN Interface

```
vlan 34
   name vrf-gold-subnet

interface Vlan34
   vrf gold
   ip address 10.34.34.2/24
   ip virtual-router address 10.34.34.1
```

### 4. Configure BGP for VRF

```
router bgp 65002
   vrf gold
      rd 10.0.250.13:1
      route-target import evpn 1:100001
      route-target export evpn 1:100001
      redistribute connected
```

### Key Concepts

- **VRF**: Virtual Routing and Forwarding instance
- **L3 VNI**: VNI for routing between VRFs
- **Anycast Gateway**: Same gateway IP/MAC on both MLAG peers
- **Type-5 Routes**: EVPN IP prefix routes for inter-subnet routing

## Best Practices

### IP Addressing
1. Use consistent /31 for P2P links
2. Reserve /32 blocks for loopbacks
3. Use non-overlapping private address space

### BGP Configuration
1. Always use peer groups for scalability
2. Set appropriate maximum-routes limits
3. Enable logging for troubleshooting
4. Use `distance bgp 20 200 200` for predictable behavior

### VXLAN/EVPN
1. Use meaningful VNI numbers (e.g., 1XXYYY where XX is VLAN/VRF)
2. Keep RD unique per device
3. Keep RT consistent across devices in same domain
4. Enable `vxlan learn-restrict any` to avoid data-plane learning

### MLAG
1. Always configure dual-active detection
2. Use trunk groups to isolate MLAG VLANs
3. Configure iBGP between peers for redundancy
4. Use consistent domain-id across pairs

### MTU
1. Set MTU to 9214 on underlay links for VXLAN overhead
2. Ensure consistent MTU across the fabric
3. Account for 50-byte VXLAN header overhead

### Security
1. Change default passwords immediately
2. Configure management VRF
3. Use authentication for BGP peers (not shown in lab configs)
4. Implement prefix-lists and route-maps in production

## Verification Checklist

After configuration, verify:

- [ ] All BGP neighbors established
- [ ] Loopbacks reachable via underlay
- [ ] EVPN routes being exchanged
- [ ] MLAG state is Active
- [ ] VXLAN interface is up
- [ ] Remote VTEPs discovered
- [ ] MAC addresses learned via EVPN
- [ ] VRF routing working end-to-end

Refer to [validation-commands.md](validation-commands.md) for detailed verification steps.

## Troubleshooting Tips

1. **No BGP neighbors**: Check IP connectivity and firewall rules
2. **No EVPN routes**: Verify `send-community extended` is configured
3. **No MAC learning**: Check VNI mapping and route-targets
4. **MLAG not working**: Verify peer-link and domain-id match
5. **No VXLAN traffic**: Check MTU and VNI configuration

## References

- [Arista EVPN Design Guide](https://www.arista.com/en/solutions/design-guides)
- [RFC 7432 - BGP MPLS-Based Ethernet VPN](https://tools.ietf.org/html/rfc7432)
- [RFC 8365 - A Network Virtualization Overlay Solution Using EVPN](https://tools.ietf.org/html/rfc8365)
- [Original Blog Post](https://overlaid.net/2019/01/27/arista-bgp-evpn-configuration-example/)
