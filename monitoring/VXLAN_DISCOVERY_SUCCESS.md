# VXLAN Telemetry Discovery - SUCCESS! 🎉

## What We Discovered

The path `/interfaces/interface[name=Vxlan1]` **WORKS** and returns **rich VXLAN data** including Arista's `arista-exp-eos-vxlan` augmentation!

### Test Command

```bash
gnmic -a 172.16.0.25:6030 -u admin -p admin --insecure \
  get --path /interfaces/interface[name=Vxlan1]
```

### Response Structure

```json
{
  "interfaces/interface": {
    "arista-exp-eos-vxlan:arista-vxlan": {
      "config": {
        "src-ip-intf": "Loopback1",
        "udp-port": 4789,
        "mac-learn-mode": "LEARN_FROM_ANY",
        ...
      },
      "state": {
        "src-ip-intf": "Loopback1",
        "udp-port": 4789,
        ...
      },
      "vlan-to-vnis": {
        "vlan-to-vni": [
          {
            "vlan": 40,
            "vni": 110040,
            "state": {...},
            "config": {...}
          }
        ]
      }
    },
    "openconfig-interfaces:config": {...},
    "openconfig-interfaces:state": {...}
  }
}
```

## VXLAN Metrics Available

### 1. VNI-to-VLAN Mappings

From `arista-vxlan.vlan-to-vnis.vlan-to-vni[]`:

```prometheus
# Metrics will be like:
gnmic_vxlan_interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vlan{source="leaf1"}
gnmic_vxlan_interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni{source="leaf1"}
```

**Use Case**: Know which VLANs are mapped to which VNIs on each VTEP

### 2. VXLAN Source Interface

From `arista-vxlan.state.src-ip-intf`:

```prometheus
gnmic_vxlan_interfaces_interface_arista_vxlan_state_src_ip_intf{source="leaf1"} = "Loopback1"
```

**Use Case**: Verify correct loopback is used for VTEP source

### 3. VXLAN UDP Port

From `arista-vxlan.state.udp-port`:

```prometheus
gnmic_vxlan_interfaces_interface_arista_vxlan_state_udp_port{source="leaf1"} = 4789
```

**Use Case**: Verify standard VXLAN port configuration

### 4. MAC Learning Mode

From `arista-vxlan.state.mac-learn-mode`:

```prometheus
gnmic_vxlan_interfaces_interface_arista_vxlan_state_mac_learn_mode{source="leaf1"} = "LEARN_FROM_ANY"
```

**Use Case**: Verify MAC learning configuration

### 5. MLAG Configuration

From `arista-vxlan.state.mlag-shared-router-mac-config`:

```prometheus
gnmic_vxlan_interfaces_interface_arista_vxlan_state_mlag_shared_router_mac_config{source="leaf1"}
```

**Use Case**: MLAG-specific VXLAN settings

## Updated gnmic Configuration

The updated `gnmic.yaml` now includes:

```yaml
subscriptions:
  vxlan:
    paths:
      - /interfaces/interface[name=Vxlan1]
    mode: stream
    stream-mode: on_change  # Config changes are infrequent
    encoding: json_ietf
```

**Key points:**
- Uses `on_change` streaming (VNI mappings don't change often)
- Only subscribed on **leaf switches** (spines don't have VXLAN)
- Captures full Arista VXLAN augmentation

## Grafana Dashboard Queries

### VNI Count per VTEP

```promql
# Count active VNIs per leaf
count by (source, vtep) (
  gnmic_vxlan_interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni
)
```

### VNI-to-VLAN Mapping Table

Create a table visualization with:

```promql
# Show VNI -> VLAN mappings
gnmic_vxlan_interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni
```

Format columns:
- `source` = Device name
- `vlan` = VLAN ID
- `Value` = VNI number

### VXLAN Configuration Check

```promql
# Check if all leaves use Loopback1
gnmic_vxlan_interfaces_interface_arista_vxlan_state_src_ip_intf

# Check if all use standard UDP port 4789
gnmic_vxlan_interfaces_interface_arista_vxlan_state_udp_port
```

### Combined VXLAN Health Dashboard

Combine with existing metrics:

```promql
# VXLAN tunnel bandwidth
rate(gnmic_interfaces_interface_state_counters_out_octets{interface_name="Vxlan1"}[1m]) * 8

# VXLAN tunnel errors
rate(gnmic_interfaces_interface_state_counters_in_errors{interface_name="Vxlan1"}[5m])

# VXLAN interface status
gnmic_interfaces_interface_state_oper_status{interface_name="Vxlan1"}

# VNI count
count by (source) (gnmic_vxlan_interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni)

# EVPN neighbor count (VTEP reachability)
count by (source) (gnmic_bgp_neighbors_neighbor_state_session_state{afi_safi_name="L2VPN_EVPN"} == 6)
```

## Benefits Over Previous Approach

### Before (Without VXLAN Subscription)
- ✅ Vxlan1 interface traffic
- ✅ BGP EVPN neighbors
- ❌ No VNI-to-VLAN visibility
- ❌ No VXLAN config verification

### Now (With VXLAN Subscription)
- ✅ Vxlan1 interface traffic
- ✅ BGP EVPN neighbors
- ✅ **VNI-to-VLAN mappings**
- ✅ **VXLAN source interface**
- ✅ **UDP port configuration**
- ✅ **MAC learning mode**
- ✅ **MLAG VXLAN settings**

## Deployment

```bash
cd monitoring
docker-compose restart gnmic

# Verify VXLAN subscription is working
docker logs gnmic | grep vxlan

# Check metrics
curl http://localhost:9804/metrics | grep vxlan | head -20

# Expected metrics:
# gnmic_vxlan_interfaces_interface_arista_vxlan_state_src_ip_intf{...}
# gnmic_vxlan_interfaces_interface_arista_vxlan_state_udp_port{...}
# gnmic_vxlan_interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni{...}
# gnmic_vxlan_interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vlan{...}
```

## Why This Works

1. **Arista augments OpenConfig** - `arista-exp-eos-vxlan` adds VXLAN-specific data to the standard interface model
2. **Vxlan1 is a real interface** - It's in the standard `/interfaces/interface` tree
3. **OpenConfig + native data** - We get both OpenConfig state AND Arista-specific VXLAN config

This is the **best of both worlds** - standard OpenConfig paths with vendor-specific augmentations!

## What About Other Native Paths?

The paths we tested that **didn't work**:
- ❌ `/Sysdb/bridging/vxlan/status` - Requires `provider eos-native`
- ❌ `/Smash/bridging/vxlan` - Not exposed via gNMI

These require additional configuration on the switches:

```
management api gnmi
   transport grpc default
      provider eos-native
```

**But we don't need them!** The Vxlan1 interface path gives us everything we need.

## Summary

🎉 **Success!** We discovered that:
1. `/interfaces/interface[name=Vxlan1]` works perfectly
2. Returns rich VXLAN data via Arista augmentations
3. Includes VNI-to-VLAN mappings, source interface, and config
4. No need for native `eos-native` provider paths

Your monitoring stack now has **complete VXLAN visibility** including:
- VXLAN tunnel traffic (already had)
- VTEP reachability via BGP EVPN (already had)
- **VNI-to-VLAN mappings (NEW!)**
- **VXLAN configuration verification (NEW!)**

**Deploy with confidence!** 🚀
