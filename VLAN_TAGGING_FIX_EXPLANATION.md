# Quick Diagnostic: Why Hosts Weren't Talking

## The Problem

You were getting **empty MAC tables and no ping replies** when testing end-to-end connectivity between hosts. The root cause was **VLAN tagging mismatch** between hosts and leaf switches.

## The Mismatch Explained

### ❌ OLD Configuration (Broken)

**Hosts were sending untagged traffic:**
```yaml
host1:
  exec:
    - ip link add bond0 type bond mode balance-rr
    - ip link set eth1 master bond0
    - ip link set eth2 master bond0
    - ip link set bond0 up
    - ip addr add 10.40.40.101/24 dev bond0    # ← UNTAGGED traffic!
```

**Leaf switches expected VLAN-tagged traffic:**
```
interface Port-Channel1
   switchport mode access
   switchport access vlan 40     # ← Expecting tagged VLAN 40!
   mlag 1
```

### Traffic Flow (Broken):
```
Host1 (untagged)
  ↓
eth1/eth2 (bonds)
  ↓
Leaf1 Port-Channel1 (access VLAN 40)
  ↓
Traffic dropped because VLAN doesn't match!
  ↗ No MAC learning
  ↗ No connectivity
```

---

## ✅ NEW Configuration (Fixed)

**Hosts now send VLAN-tagged traffic:**
```yaml
host1:
  exec:
    - ip link add bond0 type bond mode balance-rr
    - ip link set eth1 master bond0
    - ip link set eth2 master bond0
    - ip link set bond0 up
    # Create VLAN 40 subinterface
    - ip link add link bond0 name bond0.40 type vlan id 40
    - ip link set bond0.40 up
    - ip addr add 10.40.40.101/24 dev bond0.40  # ← TAGGED traffic!
```

**Leaf switches expect VLAN-tagged traffic:**
```
interface Port-Channel1
   switchport mode access
   switchport access vlan 40     # ← Now matches!
   mlag 1
```

### Traffic Flow (Fixed):
```
Host1 (VLAN 40 tagged)
  ↓
bond0.40 interface (sends tagged frames)
  ↓
eth1/eth2 (carries tagged traffic)
  ↓
Leaf1 Port-Channel1 (access VLAN 40)
  ↓
Frames untagged and placed in VLAN 40
  ↓
Switches forward in VLAN 40
  ↓
VXLAN encapsulation for remote VTEP
  ↓
✓ MAC learning works
  ✓ Connectivity established
```

---

## VLAN Tagging Mapping

| Host | Interface | VLAN Tag | Purpose | Test |
|------|-----------|----------|---------|------|
| host1 | bond0.40 | 40 | L2 VXLAN test | Ping host3 |
| host2 | bond0.34 | 34 | L3 VXLAN (VRF gold) VLAN | Ping host4 |
| host3 | bond0.40 | 40 | L2 VXLAN test | Ping host1 |
| host4 | bond0.78 | 78 | L3 VXLAN (VRF gold) VLAN | Ping host2 |

---

## Why This Works

### Layer 2 Switching Basics

When a **Linux host sends traffic on a VLAN subinterface** (e.g., `bond0.40`):
1. The interface **adds a VLAN tag (802.1Q)** to the Ethernet frame
2. Frame contains: `[Dest MAC][Source MAC][**VLAN Tag (40)**][Type][Data]`

When a **Leaf switch receives the tagged frame**:
1. It reads the VLAN tag (40)
2. The frame matches the port's access VLAN (40)
3. Frame is **untagged** and forwarded in VLAN 40
4. Switch learns MAC and floods/forwards appropriately

---

## Testing the Fix

```bash
# 1. Verify host VLAN interface exists
docker exec clab-arista-evpn-fabric-host1 ip -d link show bond0.40
# Expected: vlan protocol 802.1Q id 40 <BROADCAST,MULTICAST,UP,LOWER_UP>

# 2. Verify host has IP on VLAN interface
docker exec clab-arista-evpn-fabric-host1 ip addr show bond0.40
# Expected: inet 10.40.40.101/24 dev bond0.40

# 3. Ping the gateway (virtual router on Leaf)
docker exec clab-arista-evpn-fabric-host1 ping -c 1 10.40.40.1
# Expected: Should get reply from leaf VLAN40 gateway

# 4. Ping remote host
docker exec clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.103
# Expected: 4/4 packets successful
```

---

## Key Files Changed

1. **evpn-lab.clab.yml**
   - Updated all 4 host definitions with VLAN subinterface configuration
   - Each host now creates and configures its own VLAN tagged interface

2. **END_TO_END_TESTING.md** (new)
   - Comprehensive testing guide for all connectivity scenarios
   - Troubleshooting procedures
   - Expected results validation

---

## Why VLAN Tagging is Required Here

The topology uses **access mode port-channels on leafs** because:

1. **Each host has a single VLAN** (no trunk needed)
2. **VLAN tagging from the host side** is cleaner than reconfiguring leaf ports
3. **Matches production design** where hosts are single-VLAN attached
4. **Avoids manual leaf reconfiguration** after deployment

Alternative approach (NOT used):
- Could change leaf port-channels to trunk mode
- Would require manually configuring allowed VLANs
- More complex and less automated

This is the automated, repeatable approach that avoids manual post-deployment configuration.
