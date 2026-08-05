# gnmic

A [`gnmic`](https://gnmic.openconfig.net/) container node subscribes to gNMI (port `6030`,
`eos-native` provider) on every Arista `cEOS` node in the fabric, and exposes the
collected metrics on a Prometheus exporter endpoint.

Subscriptions:

| Subscription   | Nodes                                             | Paths                                                                                   |
| -------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `eos-interfaces` | all                                                | `interfaces/interface/state/{oper-status,counters}`                                    |
| `eos-bgp`        | all                                                | `.../bgp/neighbors/neighbor/state/session-state`, `.../afi-safis/afi-safi/state/prefixes` (IPv4/IPv6 unicast + L2VPN EVPN) |
| `eos-system`     | all                                                | `/system/cpus/cpu/state`, `/system/memory/state`                                       |
| `eos-vxlan`      | VTEP nodes only (leafs + border-leafs, both fabrics) | VLAN-to-VNI mapping + MAC table entries — joined in Prometheus to get MAC count per VNI |

- Config: `configs/gnmic/gnmic-config.yml`
- TLS: `insecure: true` — cEOS gNMI runs in plaintext here (no SSL profile configured on
  `management api gnmi`), not TLS; `skip-verify` would fail the handshake
- `oper-status` and BGP `session-state` are string enums; gnmic's Prometheus output drops
  non-numeric leaves, so the `state-to-int` event-processor maps them to `1`/`0`
- Prometheus exporter: `http://clab-arista-evpn-fabric-gnmic:9273/metrics`

```bash
# Validate gnmic is subscribed and streaming from all targets
docker logs clab-arista-evpn-fabric-gnmic

# Scrape the Prometheus exporter directly
docker exec clab-arista-evpn-fabric-gnmic wget -qO- http://localhost:9273/metrics | head
```
