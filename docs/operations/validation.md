# 🧪 Testing & Validation

## Fabric health

```bash
# DC
ssh admin@clab-arista-evpn-fabric-spine1 "show bgp evpn summary"
ssh admin@clab-arista-evpn-fabric-leaf3 "show bgp evpn summary"
ssh admin@clab-arista-evpn-fabric-dc-border-leaf1 "show bgp evpn summary"

# Campus
ssh admin@clab-arista-evpn-fabric-campus-spine1 "show bgp evpn summary"
ssh admin@clab-arista-evpn-fabric-campus-leaf1 "show bgp evpn summary"

# Core transit (no EVPN — IPv4 only)
ssh admin@clab-arista-evpn-fabric-core1 "show ip bgp summary"
ssh admin@clab-arista-evpn-fabric-core1 "show ip bgp summary vrf gold"
ssh admin@clab-arista-evpn-fabric-core1 "show ip ospf neighbor"
```

## VXLAN

```bash
# On any leaf/BL
show interface vxlan1
show vxlan vtep
show vxlan address-table
```

## MLAG

```bash
show mlag
show mlag interfaces detail
```

## Intra-DC connectivity (existing tests)

```bash
# L2 VLAN 40: dc-server1 ↔ dc-server3
docker exec -it clab-arista-evpn-fabric-host1 ping -c 3 10.40.40.103

# L3 VRF gold (DC only): dc-server2 ↔ dc-server4
docker exec -it clab-arista-evpn-fabric-host2 ping -c 3 10.78.78.104
```

## Intra-Campus connectivity

Campus hosts sit in VRF `gold` — use the L3 test to validate VTEP1↔VTEP2 via campus spines.

```bash
# L3 VRF gold (Campus only): campus-host1 ↔ campus-host2
docker exec -it clab-arista-evpn-fabric-campus-host1 ping -c 3 10.60.70.102
docker exec -it clab-arista-evpn-fabric-campus-host2 ping -c 3 10.60.60.101
```

> VLAN 50 (stretched L2 VXLAN) is still provisioned on the campus VTEPs as an
> infrastructure example but is not wired to any host in the current topology.

## End-to-end Campus ↔ DC (VRF gold via Core)

```bash
# campus-host1 (10.60.60.101, VRF gold Campus) → dc-server2 (10.34.34.102, VRF gold DC)
docker exec -it clab-arista-evpn-fabric-campus-host1 ping -c 3 10.34.34.102

# campus-host2 (10.60.70.102) → dc-server4 (10.78.78.104)
docker exec -it clab-arista-evpn-fabric-campus-host2 ping -c 3 10.78.78.104

# Reverse direction
docker exec -it clab-arista-evpn-fabric-host2 ping -c 3 10.60.60.101
docker exec -it clab-arista-evpn-fabric-host4 ping -c 3 10.60.70.102

# Traceroute: expected path campus-leaf → campus-BL → core → DC-BL → DC-leaf
docker exec -it clab-arista-evpn-fabric-campus-host1 traceroute 10.34.34.102
```

## Inspect the Core transit path

```bash
# Check VRF gold routes on core1 — both DC and Campus prefixes should be present
ssh admin@clab-arista-evpn-fabric-core1 "show ip route vrf gold"
ssh admin@clab-arista-evpn-fabric-core1 "show ip bgp vrf gold"

# EVPN Type-5 on DC-BL (imported from DC fabric, redistributed from Core into EVPN)
ssh admin@clab-arista-evpn-fabric-dc-border-leaf1 "show bgp evpn route-type ip-prefix ipv4"

# EVPN Type-5 on Campus-BL
ssh admin@clab-arista-evpn-fabric-campus-border-leaf1 "show bgp evpn route-type ip-prefix ipv4"
```

