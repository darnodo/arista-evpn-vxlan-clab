# BGP EVPN Activation Bug - Critical Fix

## Issue Description

All BGP EVPN neighbors on the leaves were stuck in **Active** state instead of **Established** state, with **0 messages sent/received**.

```
Neighbor   V AS           MsgRcvd   MsgSent  InQ OutQ  Up/Down State   PfxRcd PfxAcc
10.0.250.1 4 65000              0         0    0    0 00:02:05 Active
10.0.250.2 4 65000              0         0    0    0 00:02:05 Active
```

Active state with 0 messages means the TCP handshake was **never completed**.

## Root Cause

The **spine BGP configurations were missing the EVPN address family activation**.

In both `configs/spine1.cfg` and `configs/spine2.cfg`:

```
address-family evpn
   neighbor evpn activate     ← This line was MISSING!
```

Without activating the EVPN address family on the spines, they:
1. Accept the EVPN neighbor definitions
2. But don't actively listen for or respond to EVPN connections
3. Leaves try to establish sessions but spines don't respond
4. Connection attempt times out → Active state

This is **different from the IPv4 underlay** which was working because the IPv4 address family **was activated** on the spines.

## Solution Applied

### Before (Broken)
```
router bgp 65000
   ...
   address-family evpn
      ! Missing activation line!
```

### After (Fixed)
```
router bgp 65000
   ...
   address-family evpn
      neighbor evpn activate
```

## Files Modified

- `configs/spine1.cfg` - Added `neighbor evpn activate` in EVPN address family
- `configs/spine2.cfg` - Added `neighbor evpn activate` in EVPN address family

## Technical Explanation

In Arista EOS BGP, neighbors defined in the global BGP context don't actively participate in any address family **until explicitly activated in that address family block**.

### Address Family Activation Rules

```
router bgp 65000
   neighbor 10.0.250.1 peer group evpn
   neighbor 10.0.250.1 remote-as 65000
   
   address-family evpn
      neighbor evpn activate  ← REQUIRED for EVPN sessions to work
   
   address-family ipv4
      neighbor 10.0.250.1 activate  ← Separate activation for IPv4
```

Without activating in the EVPN address family:
- The spines define the neighbor parameters ✓
- The spines enter BGP configuration ✓
- The spines do NOT listen on TCP 179 for EVPN sessions ✗
- Leaf attempts to TCP connect to spine loopback on port 179 for EVPN ✗
- Timeout occurs → Active state ✗

## Testing the Fix

After deploying with the fix, the EVPN neighbors should immediately transition to **Established**:

```bash
# Before fix
10.0.250.1 4 65000 0 0 0 0 00:02:05 Active

# After fix
10.0.250.1 4 65000 8 8 0 0 00:00:15 Estab
```

## Impact

This was a **critical bug** that:
- Prevented any EVPN overlay from functioning
- Made L2 VXLAN testing impossible
- Made L3 VXLAN testing impossible
- Prevented MAC learning via VXLAN
- Prevented EVPN route distribution

Once fixed, the entire EVPN overlay becomes operational immediately.

## Lesson Learned

In BGP multi-address-family configurations, **every address family must be explicitly activated**. This includes:
- IPv4 unicast
- IPv6 unicast  
- EVPN
- Route target filtering
- Any other address families being used

A common mistake is to define a neighbor globally but forget to activate it in all address families where it should be used.
