# Infrahub Schema for EVPN-VXLAN Fabric

This directory contains the Infrahub schema definitions for modeling an EVPN-VXLAN fabric. The schema is designed to represent the [overlaid.net reference topology](https://overlaid.net/2019/01/27/arista-bgp-evpn-configuration-example/) (2 spines, 8 leafs in 4 MLAG pairs).

## Schema Files

| File | Nodes | Description |
|------|-------|-------------|
| `base.yml` | Device, InterfaceEthernet, InterfaceLoopback, InterfaceVlan, InterfaceLag, IPAddress, Site, Platform | Core infrastructure and generic Interface |
| `bgp.yml` | AutonomousSystem, BGPRouterConfig, BGPPeerGroup, BGPSession, BGPAddressFamily | BGP routing configuration |
| `vlan_vxlan.yml` | VLAN, VNI, VTEP, VlanVniMapping, EVPNInstance | Layer 2 overlay and VXLAN tunneling |
| `vrf.yml` | VRF, RouteTarget, VRFDeviceAssignment | VRF and L3VNI configuration |
| `mlag.yml` | MlagDomain, MlagPeerConfig, MlagInterface | MLAG domain and peer configuration |
| `extensions.yml` | Fabric, UnderlayLink, HostConnection | Fabric topology and connectivity |

## Entity Relationship Diagram

```
                          ┌──────────────┐
                          │  InfraFabric  │
                          └──────┬───────┘
                     ┌───────────┼───────────┐
                     ▼           ▼           ▼
              ┌────────────┐ ┌──────────┐ ┌──────────────────┐
              │LocationSite│ │InfraAS   │ │InfraUnderlayLink │
              └────────────┘ └────┬─────┘ │  local/remote:   │
                                  │       │  Device,Interface,│
                                  │       │  IPAddress        │
                     ┌────────────┘       └──────────────────┘
                     ▼
              ┌──────────────┐         ┌────────────────┐
              │ InfraDevice  │◄────────│ InfraPlatform  │
              └──────┬───────┘         └────────────────┘
                     │
       ┌─────────────┼──────────────┬────────────────┐
       ▼             ▼              ▼                ▼
┌─────────────┐ ┌──────────┐ ┌───────────┐  ┌──────────────┐
│InfraInterface│ │InfraBGP- │ │InfraVTEP  │  │InfraMlagDomain│
│  (generic)  │ │RouterCfg │ │           │  │ (2 devices)  │
└──────┬──────┘ └────┬─────┘ └─────┬─────┘  └──────┬───────┘
       │             │             │                │
       ▼             ▼             ▼                ▼
  Subtypes:    ┌──────────┐  ┌──────────┐   ┌───────────────┐
  - Ethernet   │BGPPeer-  │  │VlanVni-  │   │MlagPeerConfig │
  - Loopback   │  Group   │  │ Mapping  │   │  (per device) │
  - Vlan       └──────────┘  └──────────┘   └───────────────┘
  - Lag        ┌──────────┐                 ┌───────────────┐
       │       │BGPSession│                 │MlagInterface  │
       ▼       └────┬─────┘                 └───────────────┘
┌──────────────┐    │
│InfraIPAddress│    │ optional vrf
└──────────────┘    ▼
               ┌─────────┐     ┌──────────────┐
               │InfraVRF │◄────│InfraRoute-   │
               └────┬────┘     │   Target     │
                    │          └──────────────┘
                    ▼
           ┌────────────────┐
           │VRFDevice-      │
           │  Assignment    │
           │ (per device RD)│
           └────────────────┘

Layer 2 / EVPN:
┌──────────┐    ┌──────────┐    ┌──────────────┐
│InfraVLAN │◄──►│ InfraVNI │    │EVPNInstance  │
│          │    │(L2/L3)   │    │(per device   │
│          │    └──────────┘    │ RD/RT)       │
└──────────┘                    └──────────────┘
```

### Relationship Legend

| Symbol | Meaning |
|--------|---------|
| `Parent` → child | Child lifecycle depends on parent (e.g., Device → Interface) |
| `Component` → child | Owned collection (e.g., VTEP → VlanVniMapping) |
| `Attribute` | Association without ownership (e.g., BGPSession → VRF) |
| `Generic` | Polymorphic (e.g., IPAddress → any Interface subtype) |

### All Relationships

| Source | Relationship | Target | Kind | Cardinality |
|--------|-------------|--------|------|-------------|
| **base.yml** | | | | |
| InfraInterface | `device` | InfraDevice | Parent | one |
| InfraInterface | `ip_addresses` | InfraIPAddress | Generic | many |
| InfraDevice | `site` | LocationSite | Attribute | one (opt) |
| InfraDevice | `platform` | InfraPlatform | Attribute | one (opt) |
| InfraDevice | `asn` | InfraAutonomousSystem | Attribute | one (opt) |
| InfraDevice | `interfaces` | InfraInterface | Component | many |
| InfraDevice | `mlag_domain` | InfraMlagDomain | Attribute | one (opt) |
| InterfaceEthernet | `lag` | InterfaceLag | Attribute | one (opt) |
| InterfaceEthernet | `connected_interface` | InterfaceEthernet | outbound | one (opt) |
| InterfaceVlan | `vlan` | InfraVLAN | Attribute | one (opt) |
| InterfaceLag | `members` | InterfaceEthernet | Component | many |
| InfraIPAddress | `interface` | InfraInterface | Attribute | one (opt) |
| **bgp.yml** | | | | |
| BGPRouterConfig | `device` | InfraDevice | Parent | one |
| BGPRouterConfig | `local_asn` | InfraAutonomousSystem | Attribute | one |
| BGPRouterConfig | `peer_groups` | BGPPeerGroup | Component | many |
| BGPRouterConfig | `sessions` | BGPSession | Component | many |
| BGPPeerGroup | `bgp_config` | BGPRouterConfig | Parent | one |
| BGPPeerGroup | `remote_asn` | InfraAutonomousSystem | Attribute | one (opt) |
| BGPSession | `bgp_config` | BGPRouterConfig | Parent | one |
| BGPSession | `peer_group` | BGPPeerGroup | Attribute | one (opt) |
| BGPSession | `remote_asn` | InfraAutonomousSystem | Attribute | one (opt) |
| BGPSession | `peer_device` | InfraDevice | Attribute | one (opt) |
| BGPSession | `vrf` | InfraVRF | Attribute | one (opt) |
| BGPAddressFamily | `bgp_config` | BGPRouterConfig | Parent | one |
| BGPAddressFamily | `active_peer_groups` | BGPPeerGroup | Attribute | many |
| BGPAddressFamily | `networks` | InfraIPAddress | Attribute | many (opt) |
| **vlan_vxlan.yml** | | | | |
| InfraVLAN | `vni` | InfraVNI | Attribute | one (opt) |
| InfraVLAN | `site` | LocationSite | Attribute | one (opt) |
| InfraVNI | `vlan` | InfraVLAN | Attribute | one (opt) |
| InfraVNI | `vrf` | InfraVRF | Attribute | one (opt) |
| InfraVTEP | `device` | InfraDevice | Parent | one |
| InfraVTEP | `source_interface` | InterfaceLoopback | Attribute | one |
| InfraVTEP | `vlan_vni_mappings` | VlanVniMapping | Component | many |
| VlanVniMapping | `vtep` | InfraVTEP | Parent | one |
| VlanVniMapping | `vlan` | InfraVLAN | Attribute | one |
| VlanVniMapping | `vni` | InfraVNI | Attribute | one |
| EVPNInstance | `device` | InfraDevice | Parent | one |
| EVPNInstance | `vlan` | InfraVLAN | Attribute | one |
| **vrf.yml** | | | | |
| InfraVRF | `l3vni` | InfraVNI | Attribute | one (opt) |
| InfraVRF | `import_targets` | InfraRouteTarget | outbound | many (opt) |
| InfraVRF | `export_targets` | InfraRouteTarget | outbound | many (opt) |
| InfraVRF | `interfaces` | InfraInterface | Attribute | many (opt) |
| VRFDeviceAssignment | `vrf` | InfraVRF | Attribute | one |
| VRFDeviceAssignment | `device` | InfraDevice | Parent | one |
| VRFDeviceAssignment | `import_targets` | InfraRouteTarget | outbound | many (opt) |
| VRFDeviceAssignment | `export_targets` | InfraRouteTarget | outbound | many (opt) |
| **mlag.yml** | | | | |
| MlagDomain | `devices` | InfraDevice | Attribute | many (2) |
| MlagDomain | `peer_vlan` | InfraVLAN | outbound | one |
| MlagDomain | `ibgp_vlan` | InfraVLAN | outbound | one (opt) |
| MlagPeerConfig | `device` | InfraDevice | Parent | one |
| MlagPeerConfig | `mlag_domain` | MlagDomain | Attribute | one |
| MlagPeerConfig | `local_interface` | InterfaceVlan | Attribute | one |
| MlagPeerConfig | `peer_link` | InterfaceLag | Attribute | one |
| MlagInterface | `mlag_domain` | MlagDomain | Attribute | one |
| MlagInterface | `lag_interfaces` | InterfaceLag | Attribute | many (1-2) |
| **extensions.yml** | | | | |
| InfraFabric | `spine_asn` | InfraAutonomousSystem | Attribute | one (opt) |
| InfraFabric | `sites` | LocationSite | Attribute | many (opt) |
| UnderlayLink | `fabric` | InfraFabric | Parent | one |
| UnderlayLink | `local_device` | InfraDevice | outbound | one |
| UnderlayLink | `local_interface` | InterfaceEthernet | outbound | one |
| UnderlayLink | `local_ip_address` | InfraIPAddress | outbound | one |
| UnderlayLink | `remote_device` | InfraDevice | outbound | one |
| UnderlayLink | `remote_interface` | InterfaceEthernet | outbound | one |
| UnderlayLink | `remote_ip_address` | InfraIPAddress | outbound | one |
| HostConnection | `vlans` | InfraVLAN | Attribute | many |
| HostConnection | `mlag_interface` | MlagInterface | Attribute | one (opt) |
| HostConnection | `lag_interface` | InterfaceLag | Attribute | one (opt) |

## Reference Topology Mapping

| Physical | Infrahub Model |
|----------|----------------|
| spine1, spine2 | InfraDevice (role: spine) |
| leaf1-8 | InfraDevice (role: leaf) |
| AS 65000 | InfraAutonomousSystem (spines) |
| AS 65001-65004 | InfraAutonomousSystem (leaf pairs) |
| AS 64999 | InfraAutonomousSystem (border router) |
| VLAN 40, 34, 78, 900 | InfraVLAN + InfraVNI |
| VLAN 4090, 4091 | InfraVLAN (vlan_type: mlag_peer/mlag_ibgp, trunk_groups, stp_enabled: false) |
| VRF gold | InfraVRF + VRFDeviceAssignment (per-device RD) |
| Route targets 1:100001 | InfraRouteTarget |
| leaf1+leaf2 pair | InfraMlagDomain |
| Port-Channel999 | InfraInterfaceLag (peer-link) |
| Port-Channel1 | InfraMlagInterface (host-facing) |
| Ethernet1-12 | InfraInterfaceEthernet |
| Loopback0 | InfraInterfaceLoopback (BGP router-id) |
| Loopback1 | InfraInterfaceLoopback (shared VTEP IP per MLAG pair) |
| Vxlan1 | InfraVTEP |
| Vlan34/78 SVIs | InfraInterfaceVlan (virtual_router_address for anycast gateway) |
| peer groups (underlay, evpn, underlay_ibgp) | InfraBGPPeerGroup |
| BGP sessions (global) | InfraBGPSession (vrf: null) |
| BGP sessions in VRF gold (leaf7/8 → AS 64999) | InfraBGPSession (vrf: gold) |
| spine1/2 p2p links | InfraUnderlayLink (IPAddress relations, not attributes) |
| distance bgp 20 200 200 | BGPRouterConfig (ebgp_distance, ibgp_distance, local_distance) |

## Usage

### Loading the Schema

```bash
infrahubctl schema load schemas/
```

### Validation

```bash
infrahubctl schema check schemas/
```

## Key Design Decisions

1. **Generic Interface**: All interface types inherit from `InfraInterface` generic for polymorphic queries
2. **MLAG as Domain**: MLAG is modeled as a domain containing exactly 2 devices, with per-device config via MlagPeerConfig
3. **BGP Hierarchy**: BGPRouterConfig → PeerGroups → Sessions allows template-based configuration
4. **BGP VRF Sessions**: BGPSession has an optional `vrf` relation (kind: Attribute) to support peering inside a VRF context (#50)
5. **VTEP as single model**: VTEP is the unique VXLAN model (InterfaceVxlan was removed to avoid duplication — #44)
6. **EVPN Instance per VLAN**: Allows device-specific RD/RT while referencing common VLAN/VNI
7. **Per-device scoped IDs**: BGPPeerGroup and BGPSession use `bgp_config__router_id__value` prefix in human_friendly_id for global uniqueness (#43)
8. **UnderlayLink IPs as relations**: local/remote IPs reference InfraIPAddress objects instead of inline attributes to avoid dual source of truth (#47)
9. **VRFDeviceAssignment**: Separates VRF definition (global) from per-device assignment (with device-specific RD/RT overrides)
10. **Anycast gateway**: InterfaceVlan has `virtual_router_address` for `ip virtual-router address` and `autostate` for MLAG SVIs (#46)

## Related Issues

- Parent issue: [#41 — Define Infrahub Schema for EVPN-VXLAN Fabric](https://gitea.arnodo.fr/Damien/fabric-orchestrator/issues/41)
- Schema fixes: #43 (unique IDs), #44 (remove duplicate VTEP), #45 (VLAN unique), #46 (anycast gateway), #47 (underlay IPs), #48 (BGP distance), #49 (trunk groups), #50 (VRF BGP sessions)
- Depends on: Schema being loaded before transforms (#30, #31, #32, #33)
