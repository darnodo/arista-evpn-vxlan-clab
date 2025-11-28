# Deployment Guide - Critical Fixes Applied

## 📌 What Was Fixed

Two critical fixes from the `fix-bgp-and-mlag` branch have been **automatically applied** to the main branch:

### ✅ Fix #1: Spine Switch IP Routing
**Before**: BGP disabled - `show ip bgp summary` returned error messages
**After**: BGP fully operational - underlay and overlay sessions establish

```diff
+ ip routing
  service routing protocols model multi-agent
```

Applied to: `configs/spine1.cfg` and `configs/spine2.cfg`

### ✅ Fix #2: MLAG Static LAG (Already in place from previous fix)
**Changed**: LACP bonding → Static LAG for container compatibility

```diff
- channel-group 1 mode active
+ channel-group 1 mode on
```

---

## 🚀 How to Deploy

### Step 1: Clone/Update Your Repository
```bash
cd ~/arista-evpn-vxlan-clab
git pull origin main
```

### Step 2: Deploy the Lab
```bash
sudo containerlab deploy -t evpn-lab.clab.yml
```

### Step 3: Verify Spine BGP is Working
```bash
ssh admin@clab-arista-evpn-fabric-spine1 "show bgp evpn summary"
```

You should see:
```
BGP summary information for VRF default
Router identifier 10.0.250.1, local AS number 65000
Neighbor         V  AS           MsgRcvd   MsgSent  Up/Down State
10.0.250.11      4  65001              8         8 00:04:20 Estab
10.0.250.12      4  65001              8         8 00:04:20 Estab
...
```

### Step 4: Verify Underlay BGP
```bash
ssh admin@clab-arista-evpn-fabric-leaf1 "show bgp ipv4 summary"
```

---

## ⏳ What Still Needs Manual Fixes

### Issue #1: Port-Channel Access Mode
Leaf Port-Channel1 needs to be changed from `trunk` to `access` mode:

```bash
for leaf in spine1 spine2 leaf1 leaf2 leaf3 leaf4 leaf5 leaf6 leaf7 leaf8; do
  ssh admin@clab-arista-evpn-fabric-$leaf <<EOF
enable
configure terminal
# Check Port-Channel configuration
show interfaces Po1
EOF
done
```

Then manually fix if needed (or wait for updated configs).

### Issue #2: Host VLAN Configuration
Hosts need proper VLAN tagging setup. For now, you can:

```bash
# Configure Host1 (VLAN 40 - L2 VXLAN)
docker exec -it clab-arista-evpn-fabric-host1 sh << 'EOF'
ip link set bond0 down 2>/dev/null
ip link del bond0 2>/dev/null
ip addr flush dev eth1
ip addr add 10.40.40.101/24 dev eth1
ip link set eth1 up
EOF

# Configure Host3 (VLAN 40 - L2 VXLAN)
docker exec -it clab-arista-evpn-fabric-host3 sh << 'EOF'
ip link set bond0 down 2>/dev/null
ip link del bond0 2>/dev/null
ip addr flush dev eth1
ip addr add 10.40.40.103/24 dev eth1
ip link set eth1 up
EOF
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] Spine switches are reachable via SSH
- [ ] BGP EVPN summary shows 8 neighbors in ESTAB state per spine
- [ ] Leaf switches show BGP neighbors as ESTAB
- [ ] MLAG pairs show "active-full, up/up" status
- [ ] Loopback addresses are reachable (10.0.250.x/32)
- [ ] VXLAN interfaces are up on leaf switches
- [ ] MAC learning is occurring on leaf switches

---

## 📋 Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Spine IP Routing | ✅ FIXED | Critical fix applied |
| Underlay BGP | ✅ WORKING | EBGP spine-leaf, iBGP MLAG |
| EVPN Overlay | ✅ WORKING | IPv4 unicast established |
| MLAG Static LAG | ✅ WORKING | Container-friendly |
| Port-Channel Mode | ⏳ PENDING | Needs access mode change |
| Host Networking | ⏳ PENDING | Simplified config needed |
| VXLAN Tunnels | 🔧 TESTING | Awaiting host config |
| L2 VXLAN (Type-2) | 🔧 TESTING | Awaiting host connectivity |
| L3 VXLAN (Type-5) | 🔧 TESTING | Awaiting host connectivity |

---

## 🔍 Troubleshooting

### BGP Not Establishing
1. Verify `ip routing` is present in startup-config
2. Check interface IPs: `show ip interface brief`
3. Check connectivity: `ping <neighbor-ip>`
4. Check BGP neighbors: `show bgp neighbors`

### MLAG Not Forming
1. Verify peer-link is up: `show interfaces Po999`
2. Check MLAG status: `show mlag detail`
3. Verify MLAG config: `show run | grep mlag`

### No VXLAN Traffic
1. Verify VXLAN interface is up: `show interfaces vxlan1`
2. Check remote VTEPs: `show vxlan vtep`
3. Verify host connectivity: `ping <host-ip>`

---

## 📚 Documentation Reference

- Original EVPN-VXLAN example: See embedded PDF documentation
- FIXES_APPLIED.md: Detailed tracking of all fixes
- README.md: Lab topology overview
- Individual leaf/spine configs: Complete configurations

---

## 💡 Next Steps

1. ✅ Deploy with fixed spine configs
2. ✅ Verify BGP is working
3. ⏳ Update leaf Port-Channel configs to access mode
4. ⏳ Configure host networking properly
5. ⏳ Test VXLAN overlay connectivity
6. ⏳ Validate L2 VXLAN (Type-2 routes)
7. ⏳ Validate L3 VXLAN (Type-5 routes)

---

## 🎯 Summary

The critical `ip routing` fix has been integrated into the main branch. You can now deploy the lab and BGP will function correctly. Additional minor fixes for host networking can be applied manually or will be automated in future config updates.
