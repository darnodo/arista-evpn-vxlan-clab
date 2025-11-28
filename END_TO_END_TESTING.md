# End-to-End Connectivity Testing Guide

## Overview
This document provides a step-by-step guide to test the EVPN VXLAN fabric after deploying the updated topology with proper VLAN tagging on hosts.

## Recent Changes

### Fixed Issues
1. **Host VLAN Tagging** ✅
   - Hosts now create VLAN subinterfaces on top of bonded interfaces
   - Host1 & Host3: VLAN 40 tagged (L2 VXLAN test)
   - Host2: VLAN 34 tagged (L3 VXLAN test)
   - Host4: VLAN 78 tagged (L3 VXLAN test)

2. **Leaf Port-Channel Configuration** ✅
   - All leaf Port-Channel1 interfaces are in **access mode**
   - Properly mapped to their respective VLANs
   - MLAG enabled for dual-active forwarding

## Pre-Test Verification

### 1. Check MLAG Status on All Leaf Pairs

```bash
# Leaf Pair 1 (leaf1 & leaf2)
ssh admin@clab-arista-evpn-fabric-leaf1 "show mlag detail"
ssh admin@clab-arista-evpn-fabric-leaf2 "show mlag detail"

# Leaf Pair 2 (leaf3 & leaf4)
ssh admin@clab-arista-evpn-fabric-leaf3 "show mlag detail"
ssh admin@clab-arista-evpn-fabric-leaf4 "show mlag detail"

# Leaf Pair 3 (leaf5 & leaf6)
ssh admin@clab-arista-evpn-fabric-leaf5 "show mlag detail"
ssh admin@clab-arista-evpn-fabric-leaf6 "show mlag detail"

# Leaf Pair 4 (leaf7 & leaf8)
ssh admin@clab-arista-evpn-fabric-leaf7 "show mlag detail"
ssh admin@clab-arista-evpn-fabric-leaf8 "show mlag detail"
```

### 2. Check BGP Underlay Status

```bash
# On Spines
ssh admin@clab-arista-evpn-fabric-spine1 "show bgp ipv4 unicast summary"
ssh admin@clab-arista-evpn-fabric-spine2 "show bgp ipv4 unicast summary"

# Expected: All leaf neighbors should be in ESTABLISHED state
```

### 3. Check BGP EVPN Status

```bash
# On any leaf
ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn summary"

# Expected: Both spine neighbors should be ESTABLISHED
```

## L2 VXLAN Testing (VLAN 40)

### Hosts Involved
- **Host1** (10.40.40.101) - Connected to Leaf1/Leaf2 (VTEP1)
- **Host3** (10.40.40.103) - Connected to Leaf5/Leaf6 (VTEP3)

### Test Sequence

#### Step 1: Verify Host Network Interfaces

```bash
# Check host1 VLAN interface
docker exec clab-arista-evpn-fabric-host1 ip -d link show bond0.40
docker exec clab-arista-evpn-fabric-host1 ip addr show bond0.40

# Check host3 VLAN interface
docker exec clab-arista-evpn-fabric-host3 ip -d link show bond0.40
docker exec clab-arista-evpn-fabric-host3 ip addr show bond0.40
```

#### Step 2: Verify Leaf Port-Channel Configuration

```bash
# Leaf1 Port-Channel1
ssh admin@clab-arista-evpn-fabric-leaf1 "show interface Port-Channel1 switchport"

# Expected output:
# Switchport Mode: access
# Access Mode VLAN: 40
# Spanning Tree Portfast: enabled
```

#### Step 3: Test L2 Connectivity (Ping Test)

```bash
echo "=== L2 VXLAN Ping Test (Host1 → Host3) ==="
timeout 10 docker exec clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.103
```

#### Step 4: Verify MAC Learning

```bash
# On Leaf1 - check local MAC learning
ssh admin@clab-arista-evpn-fabric-leaf1 "show mac address-table vlan 40"

# Expected: MAC from host1 should appear on Port-Channel1

# On Leaf5 - check MAC learning
ssh admin@clab-arista-evpn-fabric-leaf5 "show mac address-table vlan 40"

# Expected: MAC from host3 should appear on Port-Channel1
```

#### Step 5: Verify VXLAN Learning

```bash
# Check remote VXLAN endpoints
ssh admin@clab-arista-evpn-fabric-leaf1 "show vxlan vtep"

# Expected: Should show VTEP3 (10.0.255.13)

# Check VXLAN address table
ssh admin@clab-arista-evpn-fabric-leaf1 "show vxlan address-table"

# Expected: Should show MACs learned via Vxlan1 interface
```

#### Step 6: Verify EVPN Type-2 Routes

```bash
# Check BGP EVPN routes on Leaf1
ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn route-type mac-ip"

# Expected:
# - Local MAC (host1) with RD 65001:110040
# - Remote MAC (host3) with RD 65003:110040 pointing to VTEP 10.0.255.13
```

## L3 VXLAN Testing (VRF gold)

### Hosts Involved
- **Host2** (10.34.34.102) - Connected to Leaf3/Leaf4 (VTEP2) in VRF gold VLAN 34
- **Host4** (10.78.78.104) - Connected to Leaf7/Leaf8 (VTEP4) in VRF gold VLAN 78

### Test Sequence

#### Step 1: Verify Host Network Interfaces

```bash
# Check host2 VLAN interface
docker exec clab-arista-evpn-fabric-host2 ip -d link show bond0.34
docker exec clab-arista-evpn-fabric-host2 ip addr show bond0.34

# Check host4 VLAN interface
docker exec clab-arista-evpn-fabric-host4 ip -d link show bond0.78
docker exec clab-arista-evpn-fabric-host4 ip addr show bond0.78
```

#### Step 2: Verify Leaf VRF VLAN Configuration

```bash
# On Leaf3
ssh admin@clab-arista-evpn-fabric-leaf3 "show vlan 34"
ssh admin@clab-arista-evpn-fabric-leaf3 "show interface Vlan34"

# Expected:
# - VLAN 34 exists
# - Vlan34 interface is in VRF gold with IP 10.34.34.2/24
# - Virtual router address 10.34.34.1 is configured
```

#### Step 3: Test L3 Connectivity (Ping Test)

```bash
echo "=== L3 VXLAN Ping Test (Host2 → Host4) ==="
timeout 10 docker exec clab-arista-evpn-fabric-host2 ping -c 4 10.78.78.104
```

#### Step 4: Verify VRF Routing Tables

```bash
# On Leaf3 - check routes in VRF gold
ssh admin@clab-arista-evpn-fabric-leaf3 "show ip route vrf gold"

# Expected: Should include routes to 10.34.34.0/24 and 10.78.78.0/24

# On Leaf4
ssh admin@clab-arista-evpn-fabric-leaf4 "show ip route vrf gold"
```

#### Step 5: Verify EVPN Type-5 Routes

```bash
# Check BGP EVPN routes on Leaf3
ssh admin@clab-arista-evpn-fabric-leaf3 "show bgp evpn route-type ip-prefix ipv4"

# Expected:
# - Local subnets (10.34.34.0/24 from Leaf3/Leaf4)
# - Remote subnets (10.78.78.0/24 from Leaf7/Leaf8)
```

## Complete End-to-End Test Script

```bash
#!/bin/bash

echo "======================================"
echo "EVPN VXLAN Fabric Testing"
echo "======================================"

# 1. Underlay connectivity
echo ""
echo "=== Testing Underlay BGP ==="
ssh admin@clab-arista-evpn-fabric-spine1 "show bgp ipv4 unicast summary" | tail -20

# 2. EVPN overlay connectivity
echo ""
echo "=== Testing EVPN Overlay ==="
ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn summary" | tail -5

# 3. L2 VXLAN connectivity
echo ""
echo "=== Testing L2 VXLAN (Host1 → Host3) ==="
timeout 10 docker exec clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.103
echo "Status: $?"

# 4. L3 VXLAN connectivity
echo ""
echo "=== Testing L3 VXLAN (Host2 → Host4) ==="
timeout 10 docker exec clab-arista-evpn-fabric-host2 ping -c 4 10.78.78.104
echo "Status: $?"

# 5. MAC learning verification
echo ""
echo "=== Verifying MAC Learning ==="
echo "Leaf1 VLAN 40:"
ssh admin@clab-arista-evpn-fabric-leaf1 "show mac address-table vlan 40"
echo ""
echo "Leaf5 VLAN 40:"
ssh admin@clab-arista-evpn-fabric-leaf5 "show mac address-table vlan 40"

# 6. VRF routing verification
echo ""
echo "=== Verifying VRF Routing ==="
echo "Leaf3 VRF gold routes:"
ssh admin@clab-arista-evpn-fabric-leaf3 "show ip route vrf gold"
```

## Troubleshooting

### Ping fails - Hosts can't reach each other

1. **Check host connectivity to leaf:**
   ```bash
   docker exec clab-arista-evpn-fabric-host1 ip route
   # Should show default route via VLAN gateway
   
   docker exec clab-arista-evpn-fabric-host1 ping -c 2 10.40.40.1
   # Should reach the virtual router gateway
   ```

2. **Check leaf port-channel status:**
   ```bash
   ssh admin@clab-arista-evpn-fabric-leaf1 "show interface Port-Channel1"
   # Should show "up, up"
   ```

3. **Check VXLAN interface status:**
   ```bash
   ssh admin@clab-arista-evpn-fabric-leaf1 "show interface Vxlan1"
   # Should show "up, up"
   ```

4. **Check MLAG status:**
   ```bash
   ssh admin@clab-arista-evpn-fabric-leaf1 "show mlag detail"
   # Should show "mlag is active"
   ```

### Empty MAC table on leafs

1. **Verify host is sending traffic:**
   ```bash
   docker exec clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.1
   # Generate some ARP/ICMP traffic
   ```

2. **Check for spanning-tree blocking:**
   ```bash
   ssh admin@clab-arista-evpn-fabric-leaf1 "show spanning-tree detail vlan 40"
   ```

### No EVPN routes exchanged

1. **Check BGP EVPN session state:**
   ```bash
   ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn summary"
   # Must show ESTABLISHED, not Connect or Active
   ```

2. **Check EVPN configuration:**
   ```bash
   ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn"
   # Look for rd and route-target configuration
   ```

## Expected Results

| Test | Expected Outcome | Status |
|------|------------------|--------|
| Spine BGP | All leaves established | ✓ Expected |
| Leaf BGP | All spines established | ✓ Expected |
| EVPN neighbors | Established with spines | ✓ Expected |
| L2 ping (Host1→Host3) | 4/4 packets successful | ✓ Expected |
| L3 ping (Host2→Host4) | 4/4 packets successful | ✓ Expected |
| MAC learning | MACs learned on Vxlan1 | ✓ Expected |
| EVPN Type-2 | Routes learned for MACs | ✓ Expected |
| EVPN Type-5 | Routes learned for subnets | ✓ Expected |

---

## Lab Deployment Steps

To deploy the lab with the fixes:

```bash
cd ~/arista-evpn-vxlan-clab
git checkout fix-bgp-and-mlag
sudo containerlab destroy -t evpn-lab.clab.yml
sudo containerlab deploy -t evpn-lab.clab.yml
```

The lab should now have:
- Proper VLAN tagging on all hosts
- Correct VXLAN VTEP configuration
- Working BGP EVPN overlay
- End-to-end connectivity between remote VTEPs
