# Fixes Applied in fix-bgp-and-mlag Branch

This branch contains critical fixes discovered during lab testing to make the EVPN-VXLAN fabric functional.

## 🔧 Fixes Applied

### 1. **Spine Switches - Enable IP Routing**
**Problem**: BGP was disabled on spine switches with error "BGP is disabled for VRF default" and "IP routing not enabled"

**Fix**: Added `ip routing` command to both spine configurations
- `configs/spine1.cfg` - Added line: `ip routing` (before `service routing protocols model multi-agent`)
- `configs/spine2.cfg` - Added line: `ip routing` (before `service routing protocols model multi-agent`)

**Impact**: This enables BGP to function properly on spines, allowing:
- Underlay BGP IPv4 Unicast sessions to establish
- EVPN BGP sessions to establish
- Route exchange between spines and leafs

### 2. **Leaf Switches - MLAG Port-Channel Mode**
**Problem**: LACP bonding (`mode active`) doesn't work properly in Alpine Linux containers due to lack of kernel module support

**Fix**: Changed from LACP to static LAG
- Changed `channel-group 1 mode active` to `channel-group 1 mode on` in all leaf configs
- This creates a static LAG that works in containerized environments

**Status**: ✅ Already applied in main branch (pushed by user)

### 3. **Leaf Switches - Port-Channel Switchport Mode** 
**Problem**: Port-Channel configured as trunk, but Alpine containers send untagged traffic

**Fix Needed**: Change Port-Channel1 from trunk to access mode on all leafs:
```
interface Port-Channel1
   switchport mode access
   switchport access vlan 40  # or appropriate VLAN for each VTEP
```

**Status**: ⚠️  **NOT YET APPLIED** - Needs manual configuration or config file update

### 4. **Host Configuration - Simplified Bonding**
**Problem**: Alpine Linux containers cannot properly configure 802.3ad LACP bonding

**Fix in topology**: Remove bonding complexity, use single interface:
```yaml
host1:
  exec:
    - ip addr add 10.40.40.101/24 dev eth1
    - ip link set eth1 up
```

**Status**: ⚠️ **NOT YET APPLIED** - topology file not updated in this branch

## 📋 Summary of Issues Found

### Issue #1: Missing `ip routing` on Spines
- **Symptoms**: 
  - `show ip bgp summary` returned "BGP is disabled for VRF default"
  - Attempting to configure BGP showed "! IP routing not enabled"
- **Root Cause**: Arista EOS requires explicit `ip routing` command to enable L3 functionality
- **Status**: ✅ **FIXED**

### Issue #2: LACP Bonding in Containers
- **Symptoms**:
  - Port-Channel showing "waiting for LACP response"  
  - Host bond interface in DOWN state
- **Root Cause**: Alpine containers don't have bonding kernel modules
- **Status**: ✅ **FIXED** (by changing to static LAG)

### Issue #3: Trunk vs Access Mode
- **Symptoms**:
  - No MAC learning on switch
  - Port-Channel counters showed traffic but no unicast packets
- **Root Cause**: Hosts send untagged traffic, switch expects tagged (trunk mode)
- **Status**: ⚠️ **NEEDS MANUAL FIX**

## 🚀 Deployment Instructions

### Option 1: Deploy with Manual Post-Configuration

1. Deploy the lab:
```bash
cd ~/arista-evpn-vxlan-clab
git checkout fix-bgp-and-mlag
sudo containerlab deploy -t evpn-lab.clab.yml
```

2. Fix Port-Channel mode on all leafs (manual):
```bash
for leaf in leaf1 leaf2 leaf3 leaf4 leaf5 leaf6 leaf7 leaf8; do
  ssh admin@clab-arista-evpn-fabric-$leaf << 'EOF'
enable
configure terminal
interface Port-Channel1
   switchport mode access
   switchport access vlan 40
write memory
EOF
done
```

3. Configure hosts (manual):
```bash
# Host1 (VLAN 40 - L2 VXLAN)
docker exec clab-arista-evpn-fabric-host1 sh -c '
ip link set bond0 down 2>/dev/null
ip link del bond0 2>/dev/null
ip addr flush dev eth1
ip addr add 10.40.40.101/24 dev eth1
ip link set eth1 up
'

# Host3 (VLAN 40 - L2 VXLAN)
docker exec clab-arista-evpn-fabric-host3 sh -c '
ip link set bond0 down 2>/dev/null
ip link del bond0 2>/dev/null
ip addr flush dev eth1
ip addr add 10.40.40.103/24 dev eth1
ip link set eth1 up
'

# Host2 (VRF gold - L3 VXLAN)
docker exec clab-arista-evpn-fabric-host2 sh -c '
ip link set bond0 down 2>/dev/null
ip link del bond0 2>/dev/null
ip addr flush dev eth1
ip addr add 10.34.34.102/24 dev eth1
ip link set eth1 up
ip route add default via 10.34.34.1
'

# Host4 (VRF gold - L3 VXLAN)
docker exec clab-arista-evpn-fabric-host4 sh -c '
ip link set bond0 down 2>/dev/null
ip link del bond0 2>/dev/null
ip addr flush dev eth1
ip addr add 10.78.78.104/24 dev eth1
ip link set eth1 up
ip route add default via 10.78.78.1
'
```

4. Verify:
```bash
# Check BGP
ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp evpn summary"

# Check VXLAN
ssh admin@clab-arista-evpn-fabric-leaf1 "show vxlan vtep"

# Test connectivity
docker exec -it clab-arista-evpn-fabric-host1 ping -c 4 10.40.40.103
docker exec -it clab-arista-evpn-fabric-host2 ping -c 4 10.78.78.104
```

### Option 2: Wait for Complete Fix

A complete fix will require:
1. ✅ Spine configs updated (DONE)
2. ⏳ All leaf Port-Channel configs updated to access mode
3. ⏳ Topology file updated to simplify host networking
4. ⏳ README updated with correct testing procedures

## 🧪 Testing Results

After applying fixes manually:
- ✅ BGP underlay sessions establish (eBGP between spine-leaf, iBGP between MLAG pairs)
- ✅ BGP EVPN overlay sessions establish
- ✅ MLAG pairs form correctly (active-full, up/up)
- ✅ MAC addresses learned locally on leaf switches
- ✅ EVPN Type-2 routes advertised (pending overlay establishment)
- ⏳ End-to-end connectivity (requires all fixes applied)

## 📝 Notes

- The `ip routing` fix is critical and must be in the startup-config for clean deployments
- Static LAG (`mode on`) is more reliable than LACP in containerized environments
- Access mode port-channels work better with simple Alpine containers
- For production environments with proper bonding support, LACP can be re-enabled

## 🔗 Related Issues

- Spine BGP not starting: Missing `ip routing` command
- MLAG port-channels not forming: LACP bonding incompatibility
- No MAC learning: Trunk vs access mode mismatch
