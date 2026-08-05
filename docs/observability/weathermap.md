# Weathermap panel generation (dashboard-as-code)

`scripts/generate_weathermap.py` builds a weathermap-ng Grafana panel from two
independent sources:

- **Topology** (nodes, links, positions) — fetched live from an external IP Fabric
  appliance.
- **Metrics** (node/link status, traffic) — from gnmic/Prometheus, in-topology (see
  [gnmic](gnmic.md) and [Prometheus](prometheus.md)).

Keeping this split in mind matters for troubleshooting: if the panel loses topology
(nodes/links missing or wrong) but metrics still look fine in Grafana Explore, the
IP Fabric side is what broke. If topology is fine but the panel shows no data, it's
the gnmic/Prometheus side — see [gnmic](gnmic.md) and [Prometheus](prometheus.md).

The IP Fabric instance backing the topology fetch runs on an evaluation license with
a limited lifetime. It will stop working at some point with no change on our side —
that's expected, not a regression to chase in this repo.

Should IP Fabric become unavailable, `evpn-lab.clab.yml` and
`evpn-lab.clab.yml.annotations.json` already describe the full lab topology
(nodes, links, positions) and are the obvious fallback source for the topology fetch.
Wiring that fallback into `generate_weathermap.py` is not done here — this page just
records the option for whoever picks it up.

Usage, credentials, environment variables and troubleshooting stay in
[`scripts/README.md`](../../scripts/README.md); this page does not duplicate them.
