# Infrahub Transforms

Jinja2 transforms that query InfraHub and produce JSON configuration payloads for the EVPN-VXLAN fabric devices.

Each transform follows the same pattern: a **GraphQL query** fetches intent data from InfraHub, and a **Jinja2 template** renders it into a structured JSON payload. Transforms are registered in `.infrahub.yml` at the repository root.

## Available Transforms

| Transform | Query | Scope |
|-----------|-------|-------|
| `vlan_yang_transform` | `vlan_intent` | VLAN definitions per device |
| `interface_yang_transform` | `interface_intent` | Physical/logical interfaces, switchport config |
| `vxlan_yang_transform` | `vxlan_intent` | VXLAN/VTEP tunnel config, VNI mappings |
| `vrf_yang_transform` | `vrf_intent` | VRF instances, L3VNI, route targets |
| `mlag_yang_transform` | `mlag_intent` | MLAG domain, peer-link, dual-primary detection |
| `bgp_yang_transform` | `bgp_intent` | BGP process, peer groups, neighbors, address families |

## Usage

All transforms take a `device_name` parameter:

```bash
# Render a single transform
infrahubctl render vlan_yang_transform device_name=leaf1
infrahubctl render interface_yang_transform device_name=leaf1
infrahubctl render vxlan_yang_transform device_name=leaf1
infrahubctl render vrf_yang_transform device_name=leaf7
infrahubctl render mlag_yang_transform device_name=leaf1
infrahubctl render bgp_yang_transform device_name=spine1
```

Devices without applicable config return `[]` (e.g. `mlag_yang_transform` on a spine, `vxlan_yang_transform` on a non-VTEP device).

## Directory Structure

```
infrahub/transforms/
├── queries/          # GraphQL .gql files
├── templates/        # Jinja2 .j2 files
└── tests/            # Unit test fixtures (mock input + expected output)
```

## Adding a New Transform

1. Create the GraphQL query in `queries/<name>_intent.gql`
2. Create the Jinja2 template in `templates/<name>_yang.j2`
3. Register both in `.infrahub.yml` (query + jinja2_transform)
4. Add test fixtures in `tests/<name>_yang/`
