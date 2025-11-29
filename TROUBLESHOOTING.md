# EVPN-VXLAN Fabric Troubleshooting Guide

This guide provides systematic troubleshooting steps for Arista EVPN-VXLAN fabrics with MLAG.

---

## 📋 Table of Contents

1. [Troubleshooting Methodology](#troubleshooting-methodology)
2. [Layer 1: Physical Connectivity](#layer-1-physical-connectivity)
3. [Layer 2: MLAG & Port-Channels](#layer-2-mlag--port-channels)
4. [Layer 3: Underlay (BGP IPv4)](#layer-3-underlay-bgp-ipv4)
5. [Layer 4: Overlay (BGP EVPN)](#layer-4-overlay-bgp-evpn)
6. [Layer 5: VXLAN Data Plane](#layer-5-vxlan-data-plane)
7. [End-to-End Traffic Flow](#end-to-end-traffic-flow)
8. [Common Issues & Solutions](#common-issues--solutions)

---

## 🔍 Troubleshooting Methodology

**Always troubleshoot bottom-up:**

```
Physical Links → MLAG → Underlay BGP → Overlay EVPN → VXLAN → Traffic Flow
```

**For each layer:**

1. ✅ Verify expected state
2. ❌ Identify issues
3. 🔧 Apply fixes
4. ♻️ Re-verify

---

## Layer 1: Physical Connectivity

### Check Interface Status

**On all switches (spines + leafs):**

```bash
# Quick overview
show interfaces status

# Detailed view of a specific interface
show interfaces Ethernet11

# Check for errors
show interfaces Ethernet11 | include error|drop|discard
```

**Expected Output:**

```
Ethernet11 is up, line protocol is up (connected)
  Hardware is Ethernet, address is 001c.7300.000b
  Internet address is 10.0.1.1/31
  MTU 9214 bytes
```

**Troubleshooting:**

- `down/down` → Physical issue (cable, peer interface)
- `up/down` → Layer 2 issue (switchport config, STP)
- Check MTU: Should be **9214** on underlay P2P links

---

## Layer 2: MLAG & Port-Channels

### 2.1 Verify MLAG Peering

**On each MLAG leaf pair (e.g., leaf1/leaf2):**

```bash
# MLAG global status
show mlag

# MLAG detailed info
show mlag detail

# MLAG interfaces
show mlag interfaces
```

**Expected Output (show mlag):**

```
MLAG Configuration:
domain-id               : leafs
local-interface         : Vlan4090
peer-address            : 10.0.199.255
peer-link               : Port-Channel999

MLAG Status:
state                   : Active
negotiation status      : Connected
peer-link status        : Up
local-int status        : Up
system-id               : 0c:1d:c0:1d:62:10
dual-primary detection  : Configured
```

**Troubleshooting:**

| Issue                     | Cause                               | Fix                                       |
| ------------------------- | ----------------------------------- | ----------------------------------------- |
| state: `Inactive`         | Peer-link down                      | Check Po999 and Ethernet10                |
| negotiation: `Connecting` | VLAN4090 issue                      | Verify IP addressing, peer-address config |
| peer-link: `Down`         | Port-Channel999 down                | Check `show port-channel 999`             |
| dual-primary: `Detected`  | Peer-link failed + heartbeat failed | Check mgmt network connectivity           |

---

### 2.2 Verify MLAG Peer-Link (Port-Channel999)

```bash
# Port-Channel status
show port-channel 999

# Detailed view
show port-channel 999 detailed

# LACP status
show lacp interface Port-Channel999
```

**Expected Output:**

```
Port Channel Port-Channel999 (Fallback State: Unconfigured):
Active Ports: Ethernet10
```

**Troubleshooting:**

- No active ports → Check `show interfaces Ethernet10`
- Wrong mode → Should be `switchport mode trunk`
- Missing VLANs → Check `switchport trunk group mlag-peer`

---

### 2.3 Verify Host-Facing Port-Channels (MLAG)

**On each leaf connected to hosts:**

```bash
# Port-Channel status
show port-channel 1

# MLAG status for Po1
show mlag interfaces Port-Channel1

# LACP neighbor
show lacp neighbor
```

**Expected Output (show port-channel 1):**

```
Port Channel Port-Channel1 (Fallback State: individual):
Active Ports: Ethernet1
```

**Expected Output (show mlag interfaces):**

```
                                            local/remote
 mlag        desc             state       local       remote          status
------ -------------- ------------- ----------- ------------ ---------------
    1          host1  active-full          Po1          Po1          up/up
```

**Troubleshooting:**

| Issue                 | Cause                        | Fix                              |
| --------------------- | ---------------------------- | -------------------------------- |
| `inactive`            | MLAG peering down            | Fix MLAG first (section 2.1)     |
| `active-partial`      | Remote Po1 down on peer leaf | Check peer leaf's Po1            |
| `configured-inactive` | Missing `mlag 1` config      | Add `mlag 1` to Po1              |
| No LACP neighbor      | Host bonding issue           | Check host: `ip link show bond0` |

---

### 2.4 Verify iBGP Peering Link (VLAN 4091)

```bash
# VLAN4091 interface status
show ip interface Vlan4091

# Ping peer
ping vrf default 10.0.3.1 source 10.0.3.0
```

**Expected:**

- Interface: `up/up`
- Ping: Successful

---

## Layer 3: Underlay (BGP IPv4)

### 3.1 Verify BGP Neighbors (Underlay)

**On Spines:**

```bash
# BGP summary
show ip bgp summary

# Specific neighbor
show ip bgp neighbor 10.0.1.1
```

**Expected Output:**

```
Neighbor         V  AS      MsgRcvd   MsgSent  InQ OutQ  Up/Down State  PfxRcd PfxAcc
10.0.1.1         4  65001       245       243    0    0 02:01:23 Estab  2      2
10.0.1.3         4  65001       245       243    0    0 02:01:20 Estab  2      2
...
```

**On Leafs:**

```bash
# BGP summary
show ip bgp summary

# Check underlay peer-group
show bgp peer-group underlay
```

**Expected neighbors:**

- eBGP to both spines (state: `Estab`)
- iBGP to MLAG peer (state: `Estab`)

---

### 3.2 Verify Loopback Reachability

**On any leaf, ping all other loopbacks:**

```bash
# Ping spine loopbacks
ping 10.0.250.1 source 10.0.250.11
ping 10.0.250.2 source 10.0.250.11

# Ping other leaf loopbacks
ping 10.0.250.13 source 10.0.250.11
ping 10.0.250.15 source 10.0.250.11
ping 10.0.250.17 source 10.0.250.11

# Ping VTEP loopbacks (important!)
ping 10.0.255.12 source 10.0.255.11
ping 10.0.255.13 source 10.0.255.11
ping 10.0.255.14 source 10.0.255.11
```

**Expected:**

- All pings successful
- RTT < 10ms (virtual environment)

**Troubleshooting:**

```bash
# Check routing table
show ip route

# Verify loopback advertisements
show ip bgp 10.0.250.13

# Check BGP is advertising loopbacks
show ip bgp neighbors 10.0.1.0 advertised-routes
```

**Common issues:**

- Missing `network 10.0.250.X/32` in BGP config
- Missing `network 10.0.255.X/32` (VTEP loopback!)
- BGP neighbor not activated in IPv4 address-family

---

### 3.3 Verify ECMP (Equal-Cost Multi-Path)

```bash
# Check routes to a remote loopback
show ip route 10.0.250.13

# Should show multiple next-hops
show ip route 10.0.250.13 detail
```

**Expected Output:**

```
 B E    10.0.250.13/32 [20/0] via 10.0.1.0, Ethernet11
                               via 10.0.2.0, Ethernet12
```

Two paths via both spines = ✅ ECMP working

---

## Layer 4: Overlay (BGP EVPN)

### 4.1 Verify EVPN Neighbors

**On Spines:**

```bash
# EVPN summary
show bgp evpn summary

# Check specific neighbor
show bgp evpn neighbor 10.0.250.11
```

**Expected:**

- All 8 leafs in `Estab` state
- PfxRcd > 0 (receiving EVPN routes)

**On Leafs:**

```bash
# EVPN summary
show bgp evpn summary
```

**Expected:**

- Both spines in `Estab` state
- PfxRcd > 0

---

### 4.2 Verify EVPN Routes

**Check EVPN route types:**

```bash
# Type-2: MAC/IP routes (L2 VXLAN)
show bgp evpn route-type mac-ip

# Type-3: IMET routes (VXLAN flood list)
show bgp evpn route-type imet

# Type-5: IP Prefix routes (L3 VXLAN)
show bgp evpn route-type ip-prefix ipv4
```

**Expected for L2 VXLAN (VLAN 40):**

```bash
show bgp evpn route-type mac-ip
```

Output should show:

- Local MACs (learned on Port-Channel1)
- Remote MACs (from other VTEPs via EVPN)

**Expected for L3 VXLAN (VRF gold):**

```bash
show bgp evpn route-type ip-prefix ipv4
```

Output should show:

- Local subnets (e.g., 10.34.34.0/24 on VTEP2)
- Remote subnets (e.g., 10.78.78.0/24 from VTEP4)

---

### 4.3 Troubleshoot EVPN Issues

**No EVPN neighbors:**

```bash
# Check if EVPN is activated
show running-config | section evpn

# Should see:
# address-family evpn
#    neighbor evpn activate
```

**No EVPN routes received:**

```bash
# Check route-target configuration
show running-config | section vlan 40

# Should have:
# vlan 40
#    rd 65001:110040
#    route-target both 40:110040
#    redistribute learned
```

**EVPN routes received but not installed:**

```bash
# Check VXLAN interface
show interfaces Vxlan1

# Verify VNI mapping
show vxlan vni
```

---

## Layer 5: VXLAN Data Plane

### 5.1 Verify VXLAN Interface

```bash
# VXLAN interface status
show interfaces Vxlan1

# VNI to VLAN mappings
show vxlan vni

# VTEP flood lists
show vxlan flood vtep

# Address table (MAC learning)
show vxlan address-table
```

**Expected Output (show interfaces Vxlan1):**

```
Vxlan1 is up, line protocol is up (connected)
  Hardware is Vxlan
  Source interface is Loopback1 and is active with 10.0.255.11
  Replication/Flood Mode is headend with Flood List Source: EVPN
  Remote MAC learning via EVPN
  VNI mapping to VLANs
  Static VLAN to VNI mapping is
    [40, 110040]
  Static VRF to VNI mapping is
    [gold, 100001]
```

**Expected Output (show vxlan vtep):**

```
Remote VTEPS for Vxlan1:

VTEP           Tunnel Type(s)
-------------- --------------
10.0.255.12    flood, unicast
10.0.255.13    flood, unicast
10.0.255.14    flood, unicast

Total number of remote VTEPS:  3
```

---

### 5.2 Verify MAC Learning

**Check local MAC learning:**

```bash
# MACs learned on Port-Channel1
show mac address-table interface Port-Channel1

# MACs learned via VXLAN
show mac address-table interface Vxlan1

# Combined view for a VLAN
show mac address-table vlan 40
```

**Expected Output:**

```
          Mac Address Table
------------------------------------------------------------------
Vlan    Mac Address       Type        Ports      Moves   Last Move
----    -----------       ----        -----      -----   ---------
  40    00c1.ab00.0011    DYNAMIC     Po1        1       0:05:23 ago
  40    00c1.ab00.0033    DYNAMIC     Vx1        1       0:05:20 ago
```

- Local host MAC → learned on **Po1**
- Remote host MAC → learned on **Vx1** (VXLAN)

---

### 5.3 Verify VXLAN Address Table

```bash
# VXLAN-specific MAC table
show vxlan address-table

# Detailed view
show vxlan address-table vlan 40
```

**Expected Output:**

```
          Vxlan Mac Address Table
----------------------------------------------------------------------
VLAN  Mac Address     Type     Prt  VTEP             Moves   Last Move
----  -----------     ----     ---  ----             -----   ---------
  40  00c1.ab00.0033  EVPN     Vx1  10.0.255.13      1       0:05:20 ago
```

Shows which remote VTEP the MAC is behind!

---

## End-to-End Traffic Flow

### Scenario: host1 (VTEP1) pings host3 (VTEP3) - L2 VXLAN

Both hosts in VLAN 40 (10.40.40.0/24)

---

#### Step 1: Host Sends Packet

**On host1:**

```bash
docker exec -it clab-arista-evpn-fabric-host1 sh

# Check bond interface
ip link show bond0

# Check VLAN interface
ip link show bond0.40

# Send ping
ping 10.40.40.103
```

**Expected:**

- bond0: `state UP`
- bond0.40: `state UP`

---

#### Step 2: Packet Arrives at leaf1 (VTEP1)

**On leaf1:**

```bash
# Check Port-Channel received the packet
show interfaces Port-Channel1 | include packets

# Check MAC learning
show mac address-table dynamic vlan 40

# Should see host1's MAC on Po1
```

**Traffic flow:**

```
host1:bond0.40 → [802.1Q VLAN 40] → leaf1:Eth1 → Po1
```

---

#### Step 3: Leaf1 Lookup & VXLAN Encapsulation

**Leaf1 checks MAC table:**

```bash
show mac address-table address 00c1.ab00.0033

# Output:
# VLAN 40, MAC 00c1.ab00.0033 → Vxlan1
```

**Leaf1 checks VXLAN address-table:**

```bash
show vxlan address-table address 00c1.ab00.0033

# Output:
# VLAN 40, MAC 00c1.ab00.0033 → VTEP 10.0.255.13
```

**Encapsulation:**

```
Original: [Eth: host1→host3][IP: 10.40.40.101→103][ICMP]

VXLAN:    [Outer IP: 10.0.255.11→10.0.255.13]
          [Outer UDP: src=random, dst=4789]
          [VXLAN Header: VNI=110040]
          [Inner Eth: host1→host3][IP: 10.40.40.101→103][ICMP]
```

---

#### Step 4: Underlay Routing

**Leaf1 routes outer packet:**

```bash
# Check route to remote VTEP
show ip route 10.0.255.13

# Output:
# via 10.0.1.0, Ethernet11  (spine1)
# via 10.0.2.0, Ethernet12  (spine2)
```

ECMP: Packet can go via spine1 OR spine2!

**Spine forwards based on outer IP:**

```bash
# On spine1
show ip route 10.0.255.13

# Output:
# via 10.0.1.5, Ethernet3  (leaf5)
```

---

#### Step 5: Packet Arrives at leaf5 (VTEP3)

**On leaf5:**

```bash
# Check VXLAN received the packet
show interfaces Vxlan1 | include packets

# VXLAN decapsulation happens automatically
```

**Decapsulation:**

```
VXLAN packet → Strip outer IP/UDP/VXLAN headers
→ Original frame: [Eth: host1→host3][IP: 10.40.40.101→103][ICMP]
```

**Leaf5 checks MAC table:**

```bash
show mac address-table address 00c1.ab00.0033

# Output:
# VLAN 40, MAC 00c1.ab00.0033 → Port-Channel1
```

---

#### Step 6: Packet Delivered to host3

```
leaf5:Vxlan1 → VLAN 40 → Po1 → Eth1 → host3:bond0.40
```

**On host3:**

```bash
docker exec -it clab-arista-evpn-fabric-host3 sh

# Check received ping
ping 10.40.40.101  # Reply should work!
```

---

### Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    L2 VXLAN Traffic Flow                        │
└─────────────────────────────────────────────────────────────────┘

host1 (10.40.40.101)                                host3 (10.40.40.103)
  │                                                        ▲
  │ 1. Send ping to 10.40.40.103                          │
  │    [VLAN 40 tag]                                      │ 6. Receive reply
  │                                                        │    [VLAN 40 tag]
  ▼                                                        │
leaf1:Po1                                            leaf5:Po1
  │                                                        ▲
  │ 2. MAC lookup:                                        │ 5. MAC lookup:
  │    00c1.ab00.0033 → Vx1 → 10.0.255.13                │    00c1.ab00.0011 → Vx1
  │                                                        │
  ▼                                                        │
leaf1:Vxlan1                                         leaf5:Vxlan1
  │                                                        ▲
  │ 3. VXLAN encap:                                       │ 4. VXLAN decap:
  │    Outer: 10.0.255.11 → 10.0.255.13                  │    Strip outer headers
  │    VNI: 110040                                        │
  │    Inner: original frame                              │
  │                                                        │
  ▼                                                        │
leaf1:Eth11 ──────► spine1 ──────► leaf5:Eth11 ──────────┘
         (underlay BGP routing)
```

---

## Common Issues & Solutions

### Issue 1: Ping Fails Between Hosts in Same VLAN

**Symptoms:**

- Host1 cannot ping Host3 (both VLAN 40)
- MACs not learning

**Troubleshooting Steps:**

```bash
# 1. Check Port-Channel
show port-channel 1
# → Should show active ports

# 2. Check VLAN config
show vlan 40
# → Should show Po1 as member

# 3. Check MAC learning
show mac address-table vlan 40
# → Should see local host MAC on Po1

# 4. Check VXLAN interface
show interfaces Vxlan1
# → Should be up/up

# 5. Check remote VTEPs
show vxlan vtep
# → Should list remote VTEPs

# 6. Check EVPN routes
show bgp evpn route-type mac-ip
# → Should see remote MACs

# 7. Check VXLAN address-table
show vxlan address-table vlan 40
# → Should see remote MACs via Vx1
```

**Common Causes:**

| Issue                | Fix                                               |
| -------------------- | ------------------------------------------------- |
| Port-Channel down    | Check LACP, add fallback config                   |
| MLAG not synced      | Fix MLAG peering (VLAN 4090)                      |
| VNI not configured   | Add `vxlan vlan 40 vni 110040`                    |
| EVPN not advertising | Add `redistribute learned` under `vlan 40` in BGP |
| Wrong route-target   | Verify RT matches on all VTEPs                    |

---

### Issue 2: Ping Fails Between VRFs (L3 VXLAN)

**Symptoms:**

- host2 (10.34.34.102) cannot ping host4 (10.78.78.104)
- Both in VRF gold

**Troubleshooting Steps:**

```bash
# 1. Check VRF routing
show ip route vrf gold

# 2. Check BGP EVPN Type-5 routes
show bgp evpn route-type ip-prefix ipv4

# 3. Check VRF VNI mapping
show vxlan vni
# → Should show VRF gold → VNI 100001

# 4. Check SVI is in VRF
show ip interface Vlan34
# → Should show "VRF: gold"

# 5. Check virtual gateway
show ip virtual-router
```

**Common Causes:**

| Issue                  | Fix                                           |
| ---------------------- | --------------------------------------------- |
| SVI not in VRF         | Add `vrf gold` under `interface Vlan34`       |
| VRF not mapped to VNI  | Add `vxlan vrf gold vni 100001`               |
| Route-target mismatch  | Verify `route-target both evpn 1:100001`      |
| BGP not redistributing | Add `redistribute connected` under `vrf gold` |

---

### Issue 3: MLAG Port-Channel Inactive

**Symptoms:**

```
show mlag interfaces
# mlag 1: configured-inactive
```

**Troubleshooting:**

```bash
# 1. Check MLAG global state
show mlag
# → Should be "Active"

# 2. Check Port-Channel on BOTH leafs
show port-channel 1

# 3. Check MLAG config on BOTH leafs
show running-config interfaces Port-Channel1
# → Should have "mlag 1"

# 4. Check peer leaf
# SSH to peer and run: show port-channel 1
```

**Fix:**

- Ensure BOTH leafs have `mlag 1` configured
- Ensure MLAG peering is up first
- Check peer leaf's Port-Channel status

---

### Issue 4: LACP Not Establishing

**Symptoms:**

```
show port-channel 1
# No Active Ports
# Configured, but inactive ports:
#    Ethernet1: waiting for LACP response
```

**Fix:**

```bash
# Add LACP fallback
configure
interface Port-Channel1
   port-channel lacp fallback timeout 5
   port-channel lacp fallback individual
```

**Verify:**

```bash
show port-channel 1
# → Should show Ethernet1 in "Active Ports" (fallback mode)

# Wait 5 seconds, check LACP
show lacp neighbor
# → Should show LACP neighbor if host is configured correctly
```

---

### Issue 5: BGP EVPN Neighbors Not Establishing

**Symptoms:**

```
show bgp evpn summary
# Neighbors stuck in "Connect" or "Active" state
```

**Troubleshooting:**

```bash
# 1. Check underlay reachability
ping 10.0.250.1 source Loopback0

# 2. Check EVPN neighbor config
show running-config | section evpn

# 3. Check if EVPN is activated
show bgp evpn neighbors 10.0.250.1
# → Look for "Address Family: evpn"

# 4. Check for BGP errors
show bgp evpn summary
show log | include BGP|EVPN
```

**Common Fixes:**

- Add `neighbor evpn activate` in `address-family evpn`
- Check `update-source Loopback0` is configured
- Verify `ebgp-multihop 3` for leaf-spine peering
- Check `send-community extended` is configured

---

## Quick Reference Commands

### Health Check Script

Run these commands on **each leaf** for quick validation:

```bash
#!/bin/bash
# Quick EVPN-VXLAN Health Check

echo "=== Physical Interfaces ==="
show interfaces status | include Ethernet[1-9]

echo "=== MLAG Status ==="
show mlag | include state|negotiation|peer-link

echo "=== BGP Underlay ==="
show ip bgp summary | include Estab|Neighbor

echo "=== BGP EVPN Overlay ==="
show bgp evpn summary | include Estab|Neighbor

echo "=== VXLAN ==="
show interfaces Vxlan1 | include "is up|Source interface"
show vxlan vtep

echo "=== Port-Channels ==="
show port-channel summary

echo "=== MAC Addresses ==="
show mac address-table count
```

---

### Traffic Flow Verification

**Test L2 VXLAN (VLAN 40):**

```bash
# On host1
ping 10.40.40.103 -c 3

# On leaf1 (VTEP1)
show mac address-table address 00c1.ab00.0033
show vxlan address-table address 00c1.ab00.0033

# On leaf5 (VTEP3)
show mac address-table address 00c1.ab00.0011
show vxlan address-table address 00c1.ab00.0011
```

**Test L3 VXLAN (VRF gold):**

```bash
# On host2
ping 10.78.78.104 -c 3

# On leaf3 (VTEP2)
show ip route vrf gold 10.78.78.0/24
show bgp evpn route-type ip-prefix ipv4 10.78.78.0/24

# On leaf7 (VTEP4)
show ip route vrf gold 10.34.34.0/24
```

---

## Additional Resources

- [Arista EVPN Design Guide](https://www.arista.com/en/solutions/design-guides)
- [Arista EOS Manual - VXLAN](https://www.arista.com/en/um-eos/eos-vxlan)
- [RFC 7432 - BGP MPLS-Based Ethernet VPN](https://datatracker.ietf.org/doc/html/rfc7432)

---

**Happy Troubleshooting! 🚀**
