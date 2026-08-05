# 🏷️ VXLAN Network Identifiers

## L2 VNI Mapping

| VLAN | Description                    | VNI    | Scope                                                  | RT        |
| ---- | ------------------------------ | ------ | ------------------------------------------------------ | --------- |
| 40   | DC L2 VXLAN (stretched)        | 110040 | DC VTEP1 (dc-leaf1/2) + VTEP3 (dc-leaf5/6)             | 40:110040 |
| 50   | Campus L2 VXLAN (stretched)    | 110050 | Campus VTEP1 (campus-leaf1/2) + VTEP2 (campus-leaf3/4) | 50:110050 |
| 34   | DC VRF gold subnet (local)     | 110034 | DC VTEP2 only (anycast GW 10.34.34.1)                  | 34:110034 |
| 78   | DC VRF gold subnet (local)     | 110078 | DC VTEP4 only (anycast GW 10.78.78.1)                  | 78:110078 |
| 60   | Campus VRF gold subnet (local) | 110060 | Campus VTEP1 only (anycast GW 10.60.60.1)              | 60:110060 |
| 70   | Campus VRF gold subnet (local) | 110070 | Campus VTEP2 only (anycast GW 10.60.70.1)              | 70:110070 |

## L3 VNI Mapping (end-to-end)

| VRF  | L3 VNI | RT       | Scope                                               |
| ---- | ------ | -------- | --------------------------------------------------- |
| gold | 100001 | 1:100001 | DC VTEP2/VTEP4/DC-BL + Campus VTEP1/VTEP2/Campus-BL |

VRF `gold` is announced over EVPN Type-5 (IP prefix) inside each fabric, and **stitched by the Core** via eBGP IPv4 unicast in VRF gold (over the `.200` dot1q subinterfaces). L3 VNI `100001` is re-used end-to-end for symmetry; RT `1:100001` is consistent across both fabrics. The Option A handoff requires one subinterface and one BGP session per VRF, so it does not scale past a handful of VRFs.

## Route Distinguisher Convention

- Leafs / BLs: `rd <Loopback0>:1` for VRF gold; `rd <Loopback0>:<vlan_id>` per L2 VLAN (e.g. `10.0.250.11:40`, `10.1.250.13:50`) — unique per device, so no RD is duplicated across an MLAG pair.
- Cores: `rd <Loopback0>:100001` for VRF gold (transit only — no EVPN, IPv4 unicast with `redistribute connected`).
