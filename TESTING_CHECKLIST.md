# Deployment & Testing Checklist

## ✅ What Was Fixed

- [x] Host VLAN tagging configuration in topology file
- [x] All 4 hosts now create VLAN subinterfaces (bond0.XX)
- [x] Leaf port-channels properly configured for access mode
- [x] BGP configuration in leafs includes `ip routing` command
- [x] MLAG configurations validated on all 4 leaf pairs
- [x] VXLAN VTEP configuration in place
- [x] EVPN overlay configuration complete

## 🚀 Deployment Steps

### 1. Check Current Branch
```bash
cd ~/arista-evpn-vxlan-clab
git branch
git status
```
Should show: `fix-bgp-and-mlag` branch

### 2. Destroy Current Lab (if running)
```bash
sudo containerlab destroy -t evpn-lab.clab.yml --cleanup
```

### 3. Deploy Fixed Lab
```bash
sudo containerlab deploy -t evpn-lab.clab.yml
# Wait 60-90 seconds for all containers to start
```

### 4. Verify Lab is Running
```bash
sudo containerlab inspect -t evpn-lab.clab.yml
```
Should show all 10 nodes (2 spines + 8 leaves + 4 hosts) as RUNNING

---

## 📋 Pre-Testing Checks (Run in Order)

### Check 1: Spine BGP Underlay
```bash
ssh admin@clab-arista-evpn-fabric-spine1 "show bgp ipv4 unicast summary"
```
**Expected:** All 8 leaf neighbors in ESTABLISHED state
```
10.0.1.1  4 65001  22  18  Estab  3
10.0.1.3  4 65001  20  17  Estab  3
10.0.1.5  4 65002  19  18  Estab  0    ← Check this, should be 0 or more
...
```

**Status:** ☐ Pass / ☐ Fail

---

### Check 2: Leaf MLAG Status
```bash
ssh admin@clab-arista-evpn-fabric-leaf1 "show mlag detail"
ssh admin@clab-arista-evpn-fabric-leaf3 "show mlag detail"
```
**Expected:** All pairs show `MLAG is active`
```
MLAG is active
Active per VLAN: yes
```

**Status:** ☐ Pass / ☐ Fail

---

### Check 3: Leaf BGP EVPN
```bash
ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn summary"
```
**Expected:** Both spine neighbors in ESTABLISHED
```
10.0.250.1  4 65000  8  9  Estab  0
10.0.250.2  4 65000  8  8  Estab  0
```

**Status:** ☐ Pass / ☐ Fail

---

### Check 4: Host VLAN Interfaces
```bash
docker exec clab-arista-evpn-fabric-host1 ip -d link show bond0.40
docker exec clab-arista-evpn-fabric-host2 ip -d link show bond0.34
docker exec clab-arista-evpn-fabric-host3 ip -d link show bond0.40
docker exec clab-arista-evpn-fabric-host4 ip -d link show bond0.78
```
**Expected:** All show VLAN tagging
```
vlan protocol 802.1Q id 40 <BROADCAST,MULTICAST,UP,LOWER_UP>
```

**Status:** ☐ Pass / ☐ Fail

---

## 🧪 Connectivity Tests

### Test 1: Host to Gateway (VLAN40)
```bash
docker exec clab-arista-evpn-fabric-host1 ping -c 2 10.40.40.1
docker exec clab-arista-evpn-fabric-host3 ping -c 2 10.40.40.1
```
**Expected:** 2/2 packets successful
**Status:** ☐ Pass / ☐ Fail
**Time:** ~5 seconds

---

### Test 2: L2 VXLAN Connectivity (Host1 → Host3)
```bash
docker exec clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.103
```
**Expected:** 4/4 packets successful
```
PING 10.40.40.103 (10.40.40.103): 56 data bytes
64 bytes from 10.40.40.103: seq=0 ttl=64 time=X.XXms
```
**Status:** ☐ Pass / ☐ Fail
**Time:** ~10 seconds

---

### Test 3: MAC Learning on Leaf1
```bash
ssh admin@clab-arista-evpn-fabric-leaf1 "show mac address-table vlan 40"
```
**Expected:** At least 1 MAC learned
```
Vlan    Mac Address       Type        Ports
40      XXXX.XXXX.XXXX   DYNAMIC     Po1
```
**Status:** ☐ Pass / ☐ Fail

---

### Test 4: Remote MAC Learning via VXLAN
```bash
ssh admin@clab-arista-evpn-fabric-leaf1 "show vxlan address-table vlan 40"
```
**Expected:** MAC from host3 learned via Vxlan1
```
VLAN  Mac Address     Type     Prt  VTEP
40    XXXX.XXXX.XXXX  EVPN     Vx1  10.0.255.13
```
**Status:** ☐ Pass / ☐ Fail

---

### Test 5: EVPN Type-2 Routes
```bash
ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn route-type mac-ip | head -20"
```
**Expected:** Both local and remote MACs advertised
```
RD: 65001:110040 mac-ip XXXX.XXXX.XXXX
                  -                -  
RD: 65003:110040 mac-ip XXXX.XXXX.XXXX
                  10.0.255.13      
```
**Status:** ☐ Pass / ☐ Fail

---

### Test 6: Host to Gateway (VLAN34)
```bash
docker exec clab-arista-evpn-fabric-host2 ping -c 2 10.34.34.1
```
**Expected:** 2/2 packets successful
**Status:** ☐ Pass / ☐ Fail
**Time:** ~5 seconds

---

### Test 7: L3 VXLAN Connectivity (Host2 → Host4)
```bash
docker exec clab-arista-evpn-fabric-host2 ping -c 4 10.78.78.104
```
**Expected:** 4/4 packets successful
**Status:** ☐ Pass / ☐ Fail
**Time:** ~10 seconds

---

### Test 8: VRF Routing on Leaf3
```bash
ssh admin@clab-arista-evpn-fabric-leaf3 "show ip route vrf gold"
```
**Expected:** Routes to both 10.34.34.0/24 and 10.78.78.0/24
```
C    10.34.34.0/24 is directly connected, Vlan34
B E  10.78.78.0/24 [200/0] via VTEP 10.0.255.14
```
**Status:** ☐ Pass / ☐ Fail

---

### Test 9: EVPN Type-5 Routes
```bash
ssh admin@clab-arista-evpn-fabric-leaf3 "show bgp evpn route-type ip-prefix ipv4"
```
**Expected:** IP prefixes for both VTEPs
```
RD: 10.0.250.13:1 ip-prefix 10.34.34.0/24
RD: 10.0.250.17:1 ip-prefix 10.78.78.0/24
```
**Status:** ☐ Pass / ☐ Fail

---

## 📊 Summary Table

| Component | Check | Expected | Actual | Status |
|-----------|-------|----------|--------|--------|
| Spine BGP | All leaves established | 8/8 ESTAB | ? | ☐ |
| Leaf MLAG | Pair status | active/active | ? | ☐ |
| EVPN | Spine peers | 2/2 ESTAB | ? | ☐ |
| Host Interfaces | VLAN tags | 4 VLAN ifaces | ? | ☐ |
| L2 Gateway | Ping host→gw | 2/2 success | ? | ☐ |
| L2 VXLAN | Host1→Host3 | 4/4 success | ? | ☐ |
| MAC Learning | Leaf1 VLAN40 | ≥1 MAC | ? | ☐ |
| Remote MACs | VXLAN table | MACs from Vx1 | ? | ☐ |
| Type-2 Routes | EVPN MACs | Local + Remote | ? | ☐ |
| L3 Gateway | Ping host→gw | 2/2 success | ? | ☐ |
| L3 VXLAN | Host2→Host4 | 4/4 success | ? | ☐ |
| VRF Routes | Leaf3 VRF gold | 2+ routes | ? | ☐ |
| Type-5 Routes | EVPN prefixes | Local + Remote | ? | ☐ |

---

## 🔧 If Tests Fail

### L2 ping fails
```bash
# 1. Check host VLAN interface
docker exec clab-arista-evpn-fabric-host1 ip addr show bond0.40
# Should show: inet 10.40.40.101/24 dev bond0.40

# 2. Check port-channel status
ssh admin@clab-arista-evpn-fabric-leaf1 "show interface Port-Channel1"
# Should show: up, up

# 3. Check VLAN 40 exists on leaf
ssh admin@clab-arista-evpn-fabric-leaf1 "show vlan 40"
# Should show: VLAN 40 exists

# 4. Check MAC learning (generate traffic)
docker exec clab-arista-evpn-fabric-host1 arping -c 3 10.40.40.1
ssh admin@clab-arista-evpn-fabric-leaf1 "show mac address-table vlan 40"
# Should show host1 MAC
```

### L3 ping fails
```bash
# 1. Check VRF VLAN interface
ssh admin@clab-arista-evpn-fabric-leaf3 "show interface Vlan34"
# Should show: up, up

# 2. Check VRF routing enabled
ssh admin@clab-arista-evpn-fabric-leaf3 "show ip route vrf gold"
# Should show routes

# 3. Check VXLAN VRF mapping
ssh admin@clab-arista-evpn-fabric-leaf3 "show interface Vxlan1"
# Should show: vxlan vrf gold vni 100001
```

---

## 📝 Notes for Next Steps

1. **If all tests pass** ✅
   - Create pull request to merge `fix-bgp-and-mlag` into `main`
   - Document the changes in FIXES_APPLIED.md
   - Update main branch documentation

2. **If specific tests fail** ⚠️
   - Review the troubleshooting section above
   - Check device logs: `show log`
   - Review configuration with `show running-config`

3. **Keep for reference**
   - END_TO_END_TESTING.md - Comprehensive testing guide
   - VLAN_TAGGING_FIX_EXPLANATION.md - Explains the root cause and fix

---

## 🎯 Success Criteria

**Lab is ready for production use when:**
- ✓ All pre-testing checks pass
- ✓ All 9 connectivity tests pass
- ✓ No errors in device logs
- ✓ MLAG is active/active on all pairs
- ✓ BGP neighbors all established
- ✓ EVPN routes being advertised
