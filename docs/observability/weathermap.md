# Weathermap panel generation (dashboard-as-code)

`scripts/generate_weathermap.py` builds a weathermap-ng Grafana panel from two
independent sources:

- **Topology** (nodes, links, port speeds): the [NetMapper](netmapper.md) read API,
  latest crawl ([#11](https://github.com/darnodo/arista-evpn-vxlan-clab/issues/11)).
  No containerlab file involved: the same script runs against a production NetMapper.
- **Metrics** (node/link status, traffic): gnmic/Prometheus, in-topology (see
  [gnmic](gnmic.md) and [Prometheus](prometheus.md)).

The result, `configs/grafana/dashboards/fabric.json`, is loaded by the in-lab Grafana
at start (see [Logs: Grafana](logs.md#grafana)).

Usage, node positions, environment variables and troubleshooting stay in
[`scripts/README.md`](../../scripts/README.md); this page does not duplicate them.
