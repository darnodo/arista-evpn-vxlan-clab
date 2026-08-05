# Troubleshooting

Systematic, bottom-up diagnostics for the DC + Core + Campus EVPN-VXLAN fabric.

```
Physical Links → Access (L2) → MLAG → Underlay BGP → Overlay EVPN → Core Transit → VXLAN Data Plane → Traffic Flow
```

For each layer: verify expected state, identify the failing component, fix, re-verify
before moving up.

Node names, addressing and VNI/RT values are documented in
[Architecture](../architecture/overview.md) and are not repeated here except where a
specific value is needed for a command.

## Layer 1: Physical Connectivity

```bash
show interfaces status
show interfaces Ethernet11
show interfaces Ethernet11 | include error|drop|discard
```

<!-- CAPTURE: show interfaces status on dc-leaf1 -->

- `down/down` → cable or peer interface issue.
- `up/down` → Layer 2 issue (switchport config, STP).
- Underlay P2P links (spine↔leaf/BL, BL↔Core, Core↔Core) run MTU `9214`; check MTU
  mismatches first when an eBGP session won't come up.

## Layer 2: Access (L2-only switches)

`dc-access1`-`dc-access4` and `campus-access1`/`campus-access2` sit between the leafs
and the hosts. They run `spanning-tree mode mstp` with
`spanning-tree edge-port bpduguard default`, and are LACP-bonded to their leaf MLAG
pair over `Port-Channel10` (trunk).

- DC access switches: `Port-Channel10` (uplink, trunk) and `Port-Channel1`
  (host-facing, trunk, dual-homed via LACP).
- Campus access switches: `Port-Channel10` (uplink, trunk) and a single access port
  `Ethernet3` (`switchport mode access`, `spanning-tree bpduguard enable`) for the
  single-attached host.

```bash
# On the access switch
show port-channel 10
show spanning-tree summary

# On the leaf: the access switch's uplink terminates on the leaf's own
# Port-Channel1, which is a trunk (not an access port) carrying the VLAN(s)
# assigned to that access switch
show interfaces Port-Channel1 switchport
```

<!-- CAPTURE: show port-channel 10 on dc-access1 -->

**Troubleshooting:**

| Issue | Cause | Fix |
|-------|-------|-----|
| `Port-Channel10` no active ports | LACP not negotiating on `Ethernet1`/`Ethernet2` | Check `channel-group 10 mode active` on both uplink interfaces |
| Host VLAN missing from `Port-Channel10` | `switchport trunk allowed vlan` doesn't include the host's VLAN | Compare against [Architecture — Access Switches](../architecture/overview.md#access-switches) |
| BPDU guard err-disabled a port | Unexpected BPDU on an edge port | Investigate before re-enabling; don't disable BPDU guard |

## Layer 3: MLAG & Port-Channels

Leaf pairs, border-leaf pairs, and the leaf's host/access-facing `Port-Channel1`.

```bash
show mlag
show mlag interfaces detail
show port-channel 999
```

<!-- CAPTURE: show mlag on dc-leaf1 -->
<!-- CAPTURE: show mlag interfaces detail on dc-leaf1 -->

**MLAG peer addressing** — the peer-link SVI (`Vlan4090`) and `peer-address` are
per-pair; for example, `dc-leaf1` (`10.0.199.254/31`) peers with `dc-leaf2` at
`peer-address 10.0.199.255`. Every leaf and border-leaf pair has its own `/31` in the
peer-link SVI ranges documented in
[Architecture — Addressing](../architecture/addressing.md); don't assume one pair's
values apply to another.

**Troubleshooting:**

| Issue | Cause | Fix |
|-------|-------|-----|
| `state: Inactive` | Peer-link (`Port-Channel999`) down | Check `Ethernet10` on both peers |
| `negotiation: Connecting` | `Vlan4090` SVI issue | Verify the peer-link SVI IP and `peer-address` match the pair's own `/31` |
| `dual-primary: Detected` | Peer-link down **and** mgmt heartbeat failed | Check mgmt network reachability to the peer's `Management0` |
| `mlag 1: configured-inactive` on `Port-Channel1` | Missing `mlag 1` on one of the two leafs | Add `mlag 1` under `interface Port-Channel1` on both |

## Layer 4: Underlay (BGP IPv4)

```bash
show ip bgp summary
show bgp peer-group underlay
```

<!-- CAPTURE: show ip bgp summary on dc-leaf1 -->

Each leaf/BL peers with both spines in its fabric (`Estab`). Loopback reachability:

```bash
ping 10.0.250.13 source 10.0.250.11
ping 10.0.255.12 source 10.0.255.11
show ip route 10.0.255.12
```

<!-- CAPTURE: show ip route 10.0.255.12 on dc-leaf1 -->

Two next-hops (one per spine) confirms ECMP.

**Common issues:**

- Missing `network <Loopback0>/32` or `network <Loopback1>/32` (VTEP loopback) under
  `address-family ipv4`.
- Underlay peer-group neighbor not activated in `address-family ipv4`.

## Layer 5: Overlay (BGP EVPN)

```bash
show bgp evpn summary
```

<!-- CAPTURE: show bgp evpn summary on dc-spine1 -->

- On a DC spine: expect `Estab` with all 8 DC leafs **and** the 2 DC border leafs (10
  EVPN neighbors), not just the leafs.
- On a Campus spine: expect `Estab` with all 4 Campus leafs and the 2 Campus border
  leafs (6 EVPN neighbors).
- On a leaf/BL: expect `Estab` with both spines.

```bash
show bgp evpn route-type mac-ip
show bgp evpn route-type imet
show bgp evpn route-type ip-prefix ipv4
```

<!-- CAPTURE: show bgp evpn route-type mac-ip on dc-leaf1 -->

**Common issues:**

- No EVPN neighbors: check `neighbor evpn activate` under `address-family evpn`,
  `update-source Loopback0`, and `ebgp-multihop 3`.
- No Type-2/3 routes for a VLAN: check `redistribute learned` and `route-target both`
  under that `vlan` in `router bgp`.
- No Type-5 routes for a VRF-gold subnet: see the Core Transit layer below.

## Layer 6: Core Transit

Between the DC/Campus overlays and the VXLAN data plane sits the Core, reachable only
via eBGP on `.100`/`.200` dot1q subinterfaces — there is no IGP between a border-leaf
pair and the Core.

```bash
# On core1: OSPF adjacency exists only on the core1<->core2 link (Ethernet5.100)
show ip ospf neighbor

# eBGP to DC/Campus border leafs (AS 65005 / 66005 <-> 65500), default and gold VRF
show ip bgp summary
show ip bgp summary vrf gold

# iBGP core1 <-> core2, default and gold VRF
show bgp neighbors 10.0.200.2
show bgp neighbors vrf gold 10.0.200.131
```

<!-- CAPTURE: show ip ospf neighbor on core1 -->
<!-- CAPTURE: show ip bgp summary vrf gold on core1 -->

**Where Type-5 stitching breaks:**

| Symptom | Likely cause |
|---------|--------------|
| Local subnet never appears as a Type-5 route on its own leaf/BL | `route-target import/export evpn 1:100001` missing or mismatched under `vrf gold`, or `vxlan vrf gold vni 100001` missing on `Vxlan1` |
| Subnet present on the originating leaf but absent on the border leaf | `redistribute connected route-map <RM-GOLD-...>` missing, or the route-map's prefix-list doesn't match the SVI subnet |
| Border leaf holds the route but Core never sees it | `.200` eBGP session between the BL and Core is down — check `show ip bgp summary vrf gold` on both ends |
| Core holds routes from one fabric but not the other | Same check on the other border-leaf pair's `.200` session; each BL pair peers independently with both core routers |
| Core has both fabrics' routes but the remote fabric's BL never receives them | iBGP core1↔core2 in `vrf gold` down — check `show bgp neighbors vrf gold 10.0.200.131` on core1 |

## Layer 7: VXLAN Data Plane

```bash
show interfaces Vxlan1
show vxlan vtep
show vxlan vni
show vxlan address-table
show mac address-table vlan 40
```

<!-- CAPTURE: show interfaces Vxlan1 on dc-leaf1 -->
<!-- CAPTURE: show vxlan address-table vlan 40 on dc-leaf1 -->

A local host MAC appears on the leaf's `Port-Channel1` (the trunk toward the access
switch — not a direct host-facing access port); a remote host MAC appears on `Vxlan1`,
tied to the remote VTEP's `Loopback1` address.

**Common issues:**

| Issue | Fix |
|-------|-----|
| VNI not mapped | Add `vxlan vlan <id> vni <vni>` or `vxlan vrf gold vni 100001` under `interface Vxlan1` |
| Remote VTEP missing from `show vxlan vtep` | Check EVPN Type-3 (IMET) routes for that VLAN — see Layer 5 |
| SVI not in VRF | Add `vrf gold` under the `interface Vlan<id>` |

## Layer 8: Observability

```bash
# gnmic: confirm all targets in configs/gnmic/gnmic-config.yml are subscribed
docker logs clab-arista-evpn-fabric-gnmic

# Prometheus: confirm the gnmic exporter target is up
curl -s 'http://172.16.0.71:9090/api/v1/targets' | jq '.data.activeTargets[] | {job, health}'
```

<!-- CAPTURE: docker logs clab-arista-evpn-fabric-gnmic -->
<!-- CAPTURE: curl -s 'http://172.16.0.71:9090/api/v1/targets' | jq -->

**Common issues:**

| Issue | Cause | Fix |
|-------|-------|-----|
| gnmic subscription fails for a target | Node down, or `management api gnmi` not enabled | Check `show management api gnmi` on the node |
| A target is missing from Prometheus | Not listed in `configs/gnmic/gnmic-config.yml` `targets:` | Add it, matching the naming in `evpn-lab.clab.yml` |
| Scrape errors in Prometheus | gnmic exporter (`:9273`) not reachable from the `prometheus` container | Check both containers are on the `evpn-mgmt` network and gnmic is running |
| `oper-status`/`session-state` missing from metrics | `state-to-int` event-processor not applied | Verify `event-processors: [state-to-int]` under the `prom-output` in `gnmic-config.yml` |

## End-to-End Traffic Flow

### L2 VXLAN — dc-server1 (VTEP1) → dc-server3 (VTEP3), VLAN 40

1. `dc-server1` sends on `bond0.40` → `dc-access1:Ethernet3/4` (`Port-Channel1`,
   host-facing) → `dc-access1:Port-Channel10` (uplink) → `dc-leaf1`/`dc-leaf2`
   (`Port-Channel1`, trunk).
2. `dc-leaf1` learns the source MAC on `Port-Channel1`, looks up the destination MAC:
   local → forward on `Port-Channel1`; remote → VXLAN-encapsulate toward the remote
   VTEP's `Loopback1` (`10.0.255.13` for VTEP3) with VNI `110040`, and forward over
   ECMP via `dc-spine1`/`dc-spine2`.
3. `dc-leaf5`/`dc-leaf6` decapsulate on `Vxlan1`, forward on their own
   `Port-Channel1` → `dc-access3:Port-Channel10` → `dc-access3:Port-Channel1` →
   `dc-server3`.

```bash
docker exec -it clab-arista-evpn-fabric-dc-server1 ping -c 3 10.40.40.103
```

<!-- CAPTURE: show mac address-table vlan 40 on dc-leaf1 -->
<!-- CAPTURE: show vxlan address-table vlan 40 on dc-leaf5 -->

### L3 VXLAN, VRF gold, through the Core — campus-host1 → dc-server2

1. `campus-host1` (`10.60.60.101`) sends to `dc-server2` (`10.34.34.102`) via its
   default route, `10.60.60.1` (anycast gateway on `campus-leaf1`/`campus-leaf2`).
2. `campus-leaf1`/`campus-leaf2` route into VRF `gold`, VXLAN-encapsulate (L3 VNI
   `100001`) toward `campus-border-leaf1`/`campus-border-leaf2`'s `Loopback1`
   (`10.1.255.21`), via `campus-spine1`/`campus-spine2`.
3. `campus-border-leaf1`/`2` decapsulate, route in VRF `gold` over the `.200`
   subinterface to `core1`/`core2`.
4. `core1`/`core2` route in VRF `gold` (plain IPv4, no EVPN) over their own `.200`
   subinterface to `dc-border-leaf1`/`dc-border-leaf2`.
5. `dc-border-leaf1`/`2` re-originate the route into DC EVPN Type-5, VXLAN-encapsulate
   toward `dc-leaf3`/`dc-leaf4`'s `Loopback1` (`10.0.255.12`), via `dc-spine1`/`dc-spine2`.
6. `dc-leaf3`/`dc-leaf4` decapsulate and deliver to `dc-server2` on `Vlan34`.

```bash
docker exec -it clab-arista-evpn-fabric-campus-host1 traceroute 10.34.34.102
```

<!-- CAPTURE: traceroute 10.34.34.102 from campus-host1 -->

## Common Issues & Solutions

### Ping fails between hosts in the same VLAN (L2)

```bash
show port-channel 1
show vlan <id>
show mac address-table vlan <id>
show interfaces Vxlan1
show vxlan vtep
show bgp evpn route-type mac-ip
```

| Cause | Fix |
|-------|-----|
| Access-switch `Port-Channel10` down | Fix Layer 2 (Access) first |
| MLAG not synced | Fix Layer 3 (MLAG) first |
| VNI not configured | Add `vxlan vlan <id> vni <vni>` |
| EVPN not advertising | Add `redistribute learned` under `vlan <id>` in `router bgp` |
| Route-target mismatch | Verify `route-target both <id>:<vni>` matches on all VTEPs sharing that VLAN |

### Ping fails between VRF-gold hosts across fabrics

```bash
show ip route vrf gold
show bgp evpn route-type ip-prefix ipv4
show ip bgp vrf gold        # on core1/core2
show ip route Vlan<id>
```

See Layer 6 (Core Transit) for where the Type-5 stitching typically breaks.

### MLAG Port-Channel1 inactive

```bash
show mlag
show port-channel 1
show running-config interfaces Port-Channel1
```

Ensure both leafs in the pair have `mlag 1` under `interface Port-Channel1`, and that
MLAG peering itself (Layer 3) is `Active` first.

### BGP EVPN neighbors stuck in Connect/Active

```bash
ping <remote Loopback0> source <local Loopback0>
show running-config | section evpn
show bgp evpn summary
```

Check `neighbor evpn activate` under `address-family evpn`, `update-source Loopback0`,
`ebgp-multihop 3`, and `send-community extended`.

## Additional Resources

- [Arista EVPN Design Guide](https://www.arista.com/en/solutions/design-guides)
- [Arista EOS Manual - VXLAN](https://www.arista.com/en/um-eos/eos-vxlan)
- [RFC 7432 - BGP MPLS-Based Ethernet VPN](https://datatracker.ietf.org/doc/html/rfc7432)
