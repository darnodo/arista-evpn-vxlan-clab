# Validation

End-to-end test procedures for the DC + Core + Campus fabric, ordered by widening
scope: underlay, overlay, MLAG, intra-fabric L2/L3, then the Campus ↔ DC path
through the Core, telemetry, and finally the management plane.

Node names, addressing and VNI/RT values referenced below are documented in
[Architecture](../architecture/overview.md); this page does not repeat them except
where a specific IP is needed to run a test.

Container names follow `clab-arista-evpn-fabric-<node>`, e.g.
`clab-arista-evpn-fabric-dc-leaf1`, `clab-arista-evpn-fabric-campus-host1`.

## Underlay (DC and Campus)

Each DC leaf and border leaf peers eBGP with both `dc-spine1` and `dc-spine2` over
its two `/31` underlay links; each Campus leaf and border leaf peers with both
`campus-spine1` and `campus-spine2` the same way.

```bash
# On any DC leaf/BL
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show ip bgp summary"

# On any Campus leaf/BL
ssh admin@clab-arista-evpn-fabric-campus-leaf1 "show ip bgp summary"
```

Expect two `Estab` neighbors per node (one per spine), matching the AS numbering in
[Architecture](../architecture/overview.md).

<!-- CAPTURE: show ip bgp summary on dc-leaf1 -->
<!-- CAPTURE: show ip bgp summary on campus-leaf1 -->

Loopback reachability — Router-ID (`Loopback0`) and VTEP (`Loopback1`) loopbacks
must be reachable across the fabric:

```bash
# DC: dc-leaf1 (VTEP1) to dc-leaf3 (VTEP2)
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "ping 10.0.250.13 source 10.0.250.11"
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "ping 10.0.255.12 source 10.0.255.11"

# Campus: campus-leaf1 (VTEP1) to campus-leaf3 (VTEP2)
ssh admin@clab-arista-evpn-fabric-campus-leaf1 "ping 10.1.250.13 source 10.1.250.11"
ssh admin@clab-arista-evpn-fabric-campus-leaf1 "ping 10.1.255.12 source 10.1.255.11"
```

ECMP — a route to a remote loopback should resolve via both spines:

```bash
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show ip route 10.0.255.12"
```

<!-- CAPTURE: show ip route 10.0.255.12 on dc-leaf1 -->

Two next-hops (one via each spine's underlay interface) confirms ECMP.

## Overlay EVPN (DC and Campus)

```bash
# DC spine: expects Estab with all 8 DC leafs + 2 DC border leafs (10 EVPN neighbors)
ssh admin@clab-arista-evpn-fabric-dc-spine1 "show bgp evpn summary"

# Campus spine: expects Estab with all 4 Campus leafs + 2 Campus border leafs (6 EVPN neighbors)
ssh admin@clab-arista-evpn-fabric-campus-spine1 "show bgp evpn summary"

# Any leaf/BL: expects Estab with both spines
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show bgp evpn summary"
```

<!-- CAPTURE: show bgp evpn summary on dc-spine1 -->
<!-- CAPTURE: show bgp evpn summary on campus-spine1 -->

Route type presence:

```bash
# Type-2 (MAC/IP) and Type-3 (IMET) — VLAN 40 is stretched on dc-leaf1/2 (VTEP1) and dc-leaf5/6 (VTEP3)
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show bgp evpn route-type mac-ip"
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show bgp evpn route-type imet"

# Type-5 (IP prefix) — DC VTEP2 (VLAN 34) and DC border leafs
ssh admin@clab-arista-evpn-fabric-dc-leaf3 "show bgp evpn route-type ip-prefix ipv4"
ssh admin@clab-arista-evpn-fabric-dc-border-leaf1 "show bgp evpn route-type ip-prefix ipv4"

# Type-5 (IP prefix) — Campus VTEP1 (VLAN 60) and Campus border leafs
ssh admin@clab-arista-evpn-fabric-campus-leaf1 "show bgp evpn route-type ip-prefix ipv4"
ssh admin@clab-arista-evpn-fabric-campus-border-leaf1 "show bgp evpn route-type ip-prefix ipv4"
```

<!-- CAPTURE: show bgp evpn route-type mac-ip on dc-leaf1 -->
<!-- CAPTURE: show bgp evpn route-type ip-prefix ipv4 on dc-border-leaf1 -->

## MLAG

Leaf pairs (one per VTEP), border-leaf pairs, and the access-to-leaf uplink:

```bash
# Leaf pair, e.g. VTEP1 (dc-leaf1/dc-leaf2)
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show mlag"
ssh admin@clab-arista-evpn-fabric-dc-leaf2 "show mlag"

# DC border-leaf pair
ssh admin@clab-arista-evpn-fabric-dc-border-leaf1 "show mlag"
ssh admin@clab-arista-evpn-fabric-dc-border-leaf2 "show mlag"

# Campus border-leaf pair
ssh admin@clab-arista-evpn-fabric-campus-border-leaf1 "show mlag"
ssh admin@clab-arista-evpn-fabric-campus-border-leaf2 "show mlag"
```

<!-- CAPTURE: show mlag on dc-leaf1 -->
<!-- CAPTURE: show mlag on dc-border-leaf1 -->

Access → leaf uplink (`Port-Channel10`, LACP-bonded to both leafs in the pair):

```bash
ssh admin@clab-arista-evpn-fabric-dc-access1 "show port-channel 10"
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show mlag interfaces detail"
```

<!-- CAPTURE: show port-channel 10 on dc-access1 -->
<!-- CAPTURE: show mlag interfaces detail on dc-leaf1 -->

## L2 intra-fabric — VLAN 40

`dc-server1` (VTEP1, `10.40.40.101`) ↔ `dc-server3` (VTEP3, `10.40.40.103`), both
dual-homed via LACP through `dc-access1`/`dc-access3`.

```bash
docker exec -it clab-arista-evpn-fabric-dc-server1 ping -c 3 10.40.40.103
```

Verify MAC learning and the VXLAN address-table on `dc-leaf1` and `dc-leaf5`:

```bash
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show mac address-table vlan 40"
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show vxlan address-table vlan 40"
```

<!-- CAPTURE: show vxlan address-table vlan 40 on dc-leaf1 -->

## L3 intra-fabric — VRF gold

DC: `dc-server2` (VTEP2, VLAN 34, `10.34.34.102`) ↔ `dc-server4` (VTEP4, VLAN 78,
`10.78.78.104`).

```bash
docker exec -it clab-arista-evpn-fabric-dc-server2 ping -c 3 10.78.78.104
```

Campus: `campus-host1` (VTEP1, VLAN 60, `10.60.60.101`) ↔ `campus-host2` (VTEP2,
VLAN 70, `10.60.70.102`).

```bash
docker exec -it clab-arista-evpn-fabric-campus-host1 ping -c 3 10.60.70.102
```

Verify VRF routes on the relevant leafs:

```bash
ssh admin@clab-arista-evpn-fabric-dc-leaf3 "show ip route vrf gold"
ssh admin@clab-arista-evpn-fabric-campus-leaf1 "show ip route vrf gold"
```

<!-- CAPTURE: show ip route vrf gold on dc-leaf3 -->

## End-to-end: Campus ↔ DC through the Core

VRF `gold` is stitched across the Core via eBGP IPv4 on the `.200` dot1q
subinterfaces between each border-leaf pair and both core routers.

```bash
# campus-host1 (10.60.60.101) -> dc-server2 (10.34.34.102)
docker exec -it clab-arista-evpn-fabric-campus-host1 ping -c 3 10.34.34.102

# campus-host2 (10.60.70.102) -> dc-server4 (10.78.78.104)
docker exec -it clab-arista-evpn-fabric-campus-host2 ping -c 3 10.78.78.104

# Reverse direction
docker exec -it clab-arista-evpn-fabric-dc-server2 ping -c 3 10.60.60.101
docker exec -it clab-arista-evpn-fabric-dc-server4 ping -c 3 10.60.70.102
```

Expected traceroute path: `campus-leaf → campus-border-leaf → core → dc-border-leaf
→ dc-leaf`.

```bash
docker exec -it clab-arista-evpn-fabric-campus-host1 traceroute 10.34.34.102
```

<!-- CAPTURE: traceroute 10.34.34.102 from campus-host1 -->

Check Type-5 routes on both border-leaf pairs and the transit routes on `core1`:

```bash
# EVPN Type-5 on DC border leaf (imported from DC fabric, redistributed from Core)
ssh admin@clab-arista-evpn-fabric-dc-border-leaf1 "show bgp evpn route-type ip-prefix ipv4"

# EVPN Type-5 on Campus border leaf
ssh admin@clab-arista-evpn-fabric-campus-border-leaf1 "show bgp evpn route-type ip-prefix ipv4"

# VRF gold routes on core1 — should carry both DC (10.34.34.0/24, 10.78.78.0/24)
# and Campus (10.60.60.0/24, 10.60.70.0/24) prefixes
ssh admin@clab-arista-evpn-fabric-core1 "show ip bgp vrf gold"
ssh admin@clab-arista-evpn-fabric-core1 "show ip route vrf gold"
```

<!-- CAPTURE: show ip bgp vrf gold on core1 -->
<!-- CAPTURE: show bgp evpn route-type ip-prefix ipv4 on campus-border-leaf1 -->

## Telemetry

`gnmic` streams from all 28 targets defined in `configs/gnmic/gnmic-config.yml`
(every `arista_ceos` node in DC, Core and Campus).

```bash
docker logs clab-arista-evpn-fabric-gnmic
```

<!-- CAPTURE: docker logs clab-arista-evpn-fabric-gnmic -->

`prometheus` scrapes the gnmic exporter (`172.16.0.70:9273`) every `5s`:

```bash
curl -s 'http://172.16.0.71:9090/api/v1/targets' | jq '.data.activeTargets[].health'
```

<!-- CAPTURE: curl -s 'http://172.16.0.71:9090/api/v1/targets' | jq -->

SNMPv3 answers on every node (credentials and per-role LLDP neighbour counts:
[SNMP](../observability/snmp.md)):

```bash
docker run --rm --network evpn-mgmt alpine:3 sh -c 'apk add -q net-snmp-tools && \
  snmpwalk -v3 -l authPriv -u snmp-ro -a SHA-256 -A evpnlab-auth -x AES -X evpnlab-priv \
  172.16.0.25 1.0.8802.1.1.2.1.4.1.1.9'
```

## Management plane

Services and expected behaviour: [Management plane](../observability/management-plane.md),
[Logs](../observability/logs.md).

Services up and answering:

```bash
sudo containerlab inspect -t evpn-lab.clab.yml | grep -E "loki|alloy|grafana|tacacs|radius|dns"

curl -s http://172.16.0.72:3100/ready                                   # Loki: ready
curl -s -u admin:evpnlab-grafana http://172.16.0.74:3000/api/datasources/uid/loki/health
docker exec clab-arista-evpn-fabric-campus-host1 nslookup dc-leaf1.evpnlab.local 172.16.0.77
docker exec clab-arista-evpn-fabric-radius sh -c \
  'PATH=/opt/bin:$PATH radtest campus-user1 evpnlab-user1 127.0.0.1 0 testing123'
```

TACACS+ (any node), expect `privilege level is 15` for `admin`, `show` only for `netops`:

```bash
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show privilege"
ssh netops@clab-arista-evpn-fabric-dc-leaf1 "show privilege"     # password evpnlab-netops
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show tacacs"          # counters on 172.16.0.75 only
ssh admin@clab-arista-evpn-fabric-dc-leaf1 "show aaa methods all"
```

Local fallback: `docker stop clab-arista-evpn-fabric-tacacs`, SSH still works after
~13 s, then `docker start clab-arista-evpn-fabric-tacacs`.

802.1X / MAB on the Campus access switches, expect `SUCCESS` on `Et3`:

```bash
ssh admin@clab-arista-evpn-fabric-campus-access1 "show dot1x hosts"   # campus-user1, EAPOL
ssh admin@clab-arista-evpn-fabric-campus-access2 "show dot1x hosts"   # aa:c1:ab:60:02:01, MBA
ssh admin@clab-arista-evpn-fabric-campus-access1 "show radius"
```

Per item, on any node (all return at least one row; RADIUS only on `campus-access1-2`):

| Item            | Command                                                                     |
| --------------- | --------------------------------------------------------------------------- |
| SNMPv2c         | `show running-config sanitized \| section snmp-server`                      |
| SNMPv3          | `show snmp user`, `show snmp group`                                         |
| RADIUS          | `show radius`                                                               |
| TACACS+         | `show tacacs`                                                               |
| Local users     | `show users accounts`                                                       |
| Management APIs | `show management api gnmi`, `show management api http-commands`, `show management api netconf`, `show management ssh`, `show management telnet` |
| AAA methods     | `show aaa methods all`                                                      |
| NTP             | `show ntp associations`                                                     |
| Syslog          | `show logging`                                                              |
| DNS             | `show ip name-server`                                                       |

Logs in Loki: every node, tac_plus-ng and FreeRADIUS:

```bash
curl -s -G http://172.16.0.72:3100/loki/api/v1/label/host/values
curl -s -G http://172.16.0.72:3100/loki/api/v1/query_range \
  --data-urlencode 'query={app="freeradius"} | logfmt' --data-urlencode limit=5
```

## VLAN 50 (Campus, infrastructure only)

VLAN 50 is a Campus-local L2 VXLAN stretched between `campus-leaf1`/`campus-leaf2`
and `campus-leaf3`/`campus-leaf4` (VNI `110050`). It is not wired to any host in the
current topology — no ping test applies.
