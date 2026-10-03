# Weathermap panel generation (dashboard-as-code)

`scripts/generate_weathermap.py` builds a weathermap-ng Grafana panel from two
independent sources:

- **Topology** (nodes, links, positions) — fetched from IP Fabric. IP Fabric is no
  longer available, so the topology fetch fails. NetMapper will replace it
  ([#11](https://github.com/darnodo/arista-evpn-vxlan-clab/issues/11)).
- **Metrics** (node/link status, traffic) — from gnmic/Prometheus, in-topology (see
  [gnmic](gnmic.md) and [Prometheus](prometheus.md)).

Usage, credentials, environment variables and troubleshooting stay in
[`scripts/README.md`](../../scripts/README.md); this page does not duplicate them.
