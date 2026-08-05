# Prometheus

A `prometheus` container node (`prom/prometheus`, `172.16.0.71:9090`) scrapes the
gnmic exporter every `5s` and is deployed inside the topology (`clab deploy`/`clab
destroy`, self-contained). Metric names are kept as-is; raw
OpenConfig-flattened labels are relabeled to clean, joinable names:

| Raw label                       | Clean label       |
| -------------------------------- | ------------------ |
| `source`                         | `device`           |
| `interface_name`                 | `interface`        |
| `neighbor_neighbor_address`      | `neighbor_address` |
| `vlan_to_vni_vlan` / `entry_vlan` | `vlan`             |
| `entry_mac_address`              | `mac_address`      |
| `afi_safi_afi_safi_name`         | `afi_safi`         |

`vni` is **not** available as a native label on any gnmic-exported metric — it
only appears as the sample *value* of
`interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni`, keyed by
`(device, interface, vlan)`. Per-VNI MAC counts require a PromQL join on `vlan`
rather than a native `vni` label.

`site` (`dc`/`campus`/`core`) is also not gnmic-exported. It's added as a
Prometheus `metric_relabel_configs` rule deriving it from `device` via the
`<area>-<role><n>` naming convention regex, rather than repeating
`label_replace()` in every dashboard query.

- Config: `configs/prometheus/prometheus.yml`
- This is separate from, and does not replace, the existing external Prometheus
  instance — no cutover yet, both run in parallel pending validation

```bash
# Query the in-topology Prometheus instance
curl -s 'http://172.16.0.71:9090/api/v1/query?query=system_memory_state_used' | jq
```
