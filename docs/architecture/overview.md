# 🎯 Overview

| Zone   | Devices                                                                                |
| ------ | -------------------------------------------------------------------------------------- |
| DC     | 2 spines, 8 leafs (4 MLAG VTEPs), 2 border leafs (MLAG), 4 access switches, 4 hosts    |
| Core   | 2 core routers (iBGP AS 65500, OSPF between core1/core2 only, eBGP to DC & Campus BLs) |
| Campus | 2 spines, 4 leafs (2 MLAG VTEPs), 2 border leafs (MLAG), 2 access switches, 2 hosts    |

Key design choices:

- **eBGP** in both fabrics (underlay + EVPN overlay) between spines and leafs / border leafs.
- **eBGP** (no IGP) between each Border Leaf pair and both Core routers, over directly-connected `/31`s on dot1q subinterfaces (`.100` = default VRF underlay, `.200` = VRF `gold`). OSPF area 0 is scoped to the `core1` ↔ `core2` link only, to keep Loopback0 reachable for the loopback-sourced iBGP session between the cores.
- **MLAG** everywhere there is dual-homing at the fabric layers (leaf pairs, border-leaf pairs, access → leafs, and DC host → access).
- **Host attachment pattern**:
    - **DC hosts** (servers) are **dual-homed via LACP** to an access switch — typical DC
      server redundancy.
    - **Campus hosts** (user endpoints: PC, phone, printer) are **single-attached** to a
      Campus access switch via one plain Ethernet link. Redundancy lives at the access-switch
      layer (the access switch itself is dual-homed via LACP to its leaf MLAG pair), not at
      the host.
- **VRF `gold`** is stretched end-to-end: DC leafs (VLAN 34 / 78) ↔ DC-BL ↔ Core ↔ Campus-BL ↔ Campus leafs (VLAN 60 / 70), all sharing L3 VNI `100001`.
- **VLAN 50** remains defined as a campus-local L2 VXLAN stretched between the two Campus VTEPs (infrastructure-only, not wired to any host in the current topology).
- **Convention**: L2 VNI = `110000 + vlan_id`, L3 VNI = `100001` for VRF `gold`, RT `1:100001` in both fabrics.

## 📋 Architecture

### Node Inventory

| Zone   | Role               | Nodes                                        | AS    |
| ------ | ------------------ | -------------------------------------------- | ----- |
| DC     | Spine              | `dc-spine1`, `dc-spine2`                     | 65000 |
| DC     | Leaf VTEP1 (MLAG)  | `dc-leaf1`, `dc-leaf2`                       | 65001 |
| DC     | Leaf VTEP2 (MLAG)  | `dc-leaf3`, `dc-leaf4`                       | 65002 |
| DC     | Leaf VTEP3 (MLAG)  | `dc-leaf5`, `dc-leaf6`                       | 65003 |
| DC     | Leaf VTEP4 (MLAG)  | `dc-leaf7`, `dc-leaf8`                       | 65004 |
| DC     | Border Leaf (MLAG) | `dc-border-leaf1`, `dc-border-leaf2`         | 65005 |
| DC     | Access (L2-only)   | `dc-access1`-`dc-access4`                    | —     |
| DC     | Host               | `dc-server1`-`dc-server4`                    | —     |
| Core   | Core router        | `core1`, `core2`                             | 65500 |
| Campus | Spine              | `campus-spine1`, `campus-spine2`             | 66000 |
| Campus | Leaf VTEP1 (MLAG)  | `campus-leaf1`, `campus-leaf2`               | 66001 |
| Campus | Leaf VTEP2 (MLAG)  | `campus-leaf3`, `campus-leaf4`               | 66002 |
| Campus | Border Leaf (MLAG) | `campus-border-leaf1`, `campus-border-leaf2` | 66005 |
| Campus | Access (L2-only)   | `campus-access1`, `campus-access2`           | —     |
| Campus | Host               | `campus-host1`, `campus-host2`               | —     |

### AS Numbering

| AS    | Role                              |
| ----- | --------------------------------- |
| 65000 | DC Spine                          |
| 65001 | DC VTEP1 (dc-leaf1/2)             |
| 65002 | DC VTEP2 (dc-leaf3/4)             |
| 65003 | DC VTEP3 (dc-leaf5/6)             |
| 65004 | DC VTEP4 (dc-leaf7/8)             |
| 65005 | DC Border Leaf pair               |
| 65500 | Core (iBGP between core1 & core2) |
| 66000 | Campus Spine                      |
| 66001 | Campus VTEP1 (campus-leaf1/2)     |
| 66002 | Campus VTEP2 (campus-leaf3/4)     |
| 66005 | Campus Border Leaf pair           |

### Access Switches

| Access Switch  | Uplink Pair            | VLANs | Host         | Host attachment           |
| -------------- | ---------------------- | ----- | ------------ | ------------------------- |
| dc-access1     | dc-leaf1/2 (VTEP1)     | 40    | dc-server1   | LACP Po1 (dual-homed)     |
| dc-access2     | dc-leaf3/4 (VTEP2)     | 34    | dc-server2   | LACP Po1 (dual-homed)     |
| dc-access3     | dc-leaf5/6 (VTEP3)     | 40    | dc-server3   | LACP Po1 (dual-homed)     |
| dc-access4     | dc-leaf7/8 (VTEP4)     | 78    | dc-server4   | LACP Po1 (dual-homed)     |
| campus-access1 | campus-leaf1/2 (VTEP1) | 60    | campus-host1 | access port (single link) |
| campus-access2 | campus-leaf3/4 (VTEP2) | 70    | campus-host2 | access port (single link) |

All access switches are L2-only, LACP-bonded to their leaf MLAG pair via `Port-Channel10`. MSTP + edge-port BPDU guard.

Host-facing ports:

- **DC access switches** run a `Port-Channel1` trunk (VLANs allowed per host) for a host
  dual-homed in LACP (two physical links, one bond on the Linux side).
- **Campus access switches** use a plain `Ethernet3` in `switchport mode access` with
  BPDU guard + portfast — the host connects with a single Ethernet link and no bonding.

