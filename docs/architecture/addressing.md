# 🧭 IP Addressing Plan

## Management (`172.16.0.0/24`)

| Node            | IP             | Node                | IP               |
| --------------- | -------------- | ------------------- | ---------------- |
| dc-spine1       | 172.16.0.1     | campus-spine1       | 172.16.0.20      |
| dc-spine2       | 172.16.0.2     | campus-spine2       | 172.16.0.21      |
| dc-border-leaf1 | 172.16.0.3     | campus-border-leaf1 | 172.16.0.22      |
| dc-border-leaf2 | 172.16.0.4     | campus-border-leaf2 | 172.16.0.23      |
| core1           | 172.16.0.10    | campus-leaf1-4      | 172.16.0.51-54   |
| core2           | 172.16.0.11    | campus-access1      | 172.16.0.61      |
| dc-leaf1        | 172.16.0.25    | campus-access2      | 172.16.0.62      |
| dc-leaf2        | 172.16.0.50    | dc-server1-4        | 172.16.0.101-104 |
| dc-leaf3-8      | 172.16.0.27-32 | campus-host1        | 172.16.0.105     |
| dc-access1-4    | 172.16.0.41-44 | campus-host2        | 172.16.0.106     |
|                 |                | gnmic               | 172.16.0.70      |
|                 |                | prometheus          | 172.16.0.71      |

Gateway: `172.16.0.254`.

## Router-ID Loopback0 (`Lo0`)

| Zone   | Range           | Nodes                                                                                      |
| ------ | --------------- | ------------------------------------------------------------------------------------------ |
| DC     | `10.0.250.0/24` | dc-spine1 .1, dc-spine2 .2, dc-leaf1-8 .11-.18, BL-dc1 .21, BL-dc2 .22                     |
| Core   | `10.0.200.0/24` | core1 `10.0.200.1`, core2 `10.0.200.2`                                                     |
| Campus | `10.1.250.0/24` | campus-spine1 .1, campus-spine2 .2, campus-leaf1-4 .11-.14, BL-campus1 .21, BL-campus2 .22 |

## VTEP Loopback1 (`Lo1`) — shared per MLAG pair

| Fabric | VTEP  | Address       | Leafs                 |
| ------ | ----- | ------------- | --------------------- |
| DC     | VTEP1 | `10.0.255.11` | dc-leaf1, dc-leaf2    |
| DC     | VTEP2 | `10.0.255.12` | dc-leaf3, dc-leaf4    |
| DC     | VTEP3 | `10.0.255.13` | dc-leaf5, dc-leaf6    |
| DC     | VTEP4 | `10.0.255.14` | dc-leaf7, dc-leaf8    |
| DC     | BL    | `10.0.255.15` | dc-border-leaf1/2     |
| Campus | VTEP1 | `10.1.255.11` | campus-leaf1/2        |
| Campus | VTEP2 | `10.1.255.12` | campus-leaf3/4        |
| Campus | BL    | `10.1.255.21` | campus-border-leaf1/2 |

## Underlay P2P (`/31`)

| Segment                         | Subnets                                                |
| ------------------------------- | ------------------------------------------------------ |
| DC dc-spine1 ↔ leaf/BL          | `10.0.1.0/31` … `10.0.1.18/31`                         |
| DC dc-spine2 ↔ leaf/BL          | `10.0.2.0/31` … `10.0.2.18/31`                         |
| DC MLAG iBGP SVIs (per pair)    | `10.0.3.0/31`, `.2/31`, `.4/31`, `.6/31`, `.8/31` (BL) |
| DC MLAG peer-link SVIs          | `10.0.199.240/31` … `10.0.199.246/31`                  |
| DC-BL ↔ Core (default, `.100`)  | `10.0.4.0/31` .. `10.0.4.6/31`                         |
| DC-BL ↔ Core (VRF gold, `.200`) | `10.0.14.0/31` .. `10.0.14.6/31`                       |
| Campus-BL ↔ Core (default)      | `10.0.5.0/31` .. `10.0.5.6/31`                         |
| Campus-BL ↔ Core (VRF gold)     | `10.0.15.0/31` .. `10.0.15.6/31`                       |
| Core1 ↔ Core2 (default)         | `10.0.200.128/31`                                      |
| Core1 ↔ Core2 (VRF gold)        | `10.0.200.130/31`                                      |
| Campus dc-spine1 ↔ leaf/BL      | `10.1.1.0/31` … `10.1.1.10/31`                         |
| Campus dc-spine2 ↔ leaf/BL      | `10.1.2.0/31` … `10.1.2.10/31`                         |
| Campus MLAG iBGP SVIs           | `10.1.3.0/31`, `.2/31`, `.4/31`                        |
| Campus MLAG peer-link SVIs      | `10.1.199.250/31` … `10.1.199.254/31`                  |

## Host Addressing

| Host         | VLAN | VRF     | IP / Mask       | Gateway    | Purpose                       |
| ------------ | ---- | ------- | --------------- | ---------- | ----------------------------- |
| dc-server1   | 40   | default | 10.40.40.101/24 | —          | DC L2 stretched (VTEP1↔VTEP3) |
| dc-server2   | 34   | gold    | 10.34.34.102/24 | 10.34.34.1 | DC L3 VRF gold                |
| dc-server3   | 40   | default | 10.40.40.103/24 | —          | DC L2 stretched               |
| dc-server4   | 78   | gold    | 10.78.78.104/24 | 10.78.78.1 | DC L3 VRF gold                |
| campus-host1 | 60   | gold    | 10.60.60.101/24 | 10.60.60.1 | Campus L3 VRF gold            |
| campus-host2 | 70   | gold    | 10.60.70.102/24 | 10.60.70.1 | Campus L3 VRF gold            |

> DC hosts are dual-homed in LACP over `bond0` with tagged VLAN sub-interfaces.
> Campus hosts are single-attached with one untagged `eth1` in a single access VLAN.
