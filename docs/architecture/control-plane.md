# 🔀 Control Plane Summary

| Segment                           | Protocol                             | Notes                                |
| --------------------------------- | ------------------------------------ | ------------------------------------ |
| DC spine ↔ leaf/BL underlay       | eBGP IPv4 (AS 65000 ↔ 650xx)         | `maximum-paths 4 ecmp 64`            |
| DC spine ↔ leaf/BL overlay        | eBGP EVPN via Loopback0, multi-hop 3 | Spines reflect via `ebgp peer-group` |
| DC MLAG pair iBGP                 | iBGP over VLAN 4091 SVI              | `next-hop-self`                      |
| DC-BL ↔ Core (default)            | eBGP AS 65005 ↔ 65500                | on `.100` dot1q subinterface, no IGP |
| DC-BL ↔ Core (VRF gold)           | eBGP AS 65005 ↔ 65500                | on `.200` dot1q subinterface         |
| Core1 ↔ Core2 (default)           | OSPF area 0 + iBGP AS 65500          | via Loopback0                        |
| Core1 ↔ Core2 (VRF gold)          | iBGP AS 65500                        | VRF-aware over `.200` subinterface   |
| Campus-BL ↔ Core (default / gold) | eBGP AS 66005 ↔ 65500                | same pattern as DC-BL, no IGP        |
| Campus spine ↔ leaf/BL underlay   | eBGP IPv4 (AS 66000 ↔ 660xx)         |                                      |
| Campus spine ↔ leaf/BL overlay    | eBGP EVPN via Loopback0, multi-hop 3 |                                      |
| Campus MLAG pair iBGP             | iBGP over VLAN 4091 SVI              |                                      |
