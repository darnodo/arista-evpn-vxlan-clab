# scripts/generate_weathermap.py

Generates the **weathermap panel only** from the containerlab topology and live
Prometheus data, merges it into a hand-authored dashboard base, and writes the
dashboard that the in-lab Grafana loads at start.

## Files

| File | What it is | Edit it? |
| ---- | ---------- | -------- |
| `clab-arista-evpn-fabric/topology-data.json` | Written by `containerlab deploy`: nodes and links | No, input |
| `configs/grafana/dashboard-base.json` | Hand-authored: BGP table, ports table, throughput graphs, `site`/`device` variables, layout. One reserved slot panel (`title: "__WEATHERMAP_SLOT__"`) where the weathermap is spliced in | Yes, directly |
| `configs/grafana/dashboards/fabric.json` | Generated: base + fresh weathermap panel. Provisioned from file by the in-lab Grafana | No, regenerate instead (node positions excepted, see below) |

Topology (nodes, links) changes with the lab and is regenerated on every run; the rest
of the dashboard is hand-tuned and never touched by a topology refresh. See #52.

## Quickstart

```bash
# lab deployed, gnmic/Prometheus running
python3 scripts/generate_weathermap.py   # rewrites configs/grafana/dashboards/fabric.json
```

Grafana reads the file at start: redeploy the `grafana` node (or restart its container)
to load a new version, then commit the file. Re-run after any topology change.

`--provision` also pushes the dashboard through the Grafana API (`GRAFANA_URL`,
`GRAFANA_TOKEN`), e.g. to an external Grafana.

## Node positions

Nodes get a layered default position (Y-tier by role parsed from the hostname:
`spine -> core -> border-leaf -> leaf -> access`, X grouped by site). A position set once
is kept on later runs, read from (first match wins):

1. the live Grafana dashboard, when `GRAFANA_URL`/`GRAFANA_TOKEN` are set (#53);
2. the existing output file (`configs/grafana/dashboards/fabric.json`);
3. the layered default, for new nodes only.

To move nodes: drag them in Grafana, save, run the script with `GRAFANA_URL` and
`GRAFANA_TOKEN` (service account token, Editor role), commit `fabric.json`. UI saves alone
are lost on redeploy.

## Environment variables

| Variable | Required | Default |
| -------- | -------- | ------- |
| `PROMETHEUS_URL` | no | `http://172.16.0.71:9090` |
| `GRAFANA_URL` | with `--provision`, or to read live positions | - |
| `GRAFANA_TOKEN` | with `--provision`, or to read live positions | - |
| `GRAFANA_DATASOURCE_UID` | no | `prometheus` (UID provisioned in the in-lab Grafana) |
| `GRAFANA_DASHBOARD_UID` | no | `evpn-vxlan-fabric-weathermap` |
| `GRAFANA_WEATHERMAP_PLUGIN_ID` | no | `tamirsuliman-weathermap-panel` |
| `--topology` (CLI flag) | no | `clab-arista-evpn-fabric/topology-data.json` |
| `--base` (CLI flag) | no | `configs/grafana/dashboard-base.json` |
| `--output` (CLI flag) | no | `configs/grafana/dashboards/fabric.json` |

## Troubleshooting

| Symptom | Cause | Check |
| ------- | ----- | ----- |
| `topology-data.json not found` | Lab not deployed from this directory | `sudo containerlab inspect -t evpn-lab.clab.yml` |
| Panel renders with no data | Wrong datasource UID | Explore, run `up` against it, confirm gnmic series come back |
| Weathermap panel shows "panel plugin not found" | Plugin not installed (needs internet at Grafana start) | `docker logs clab-arista-evpn-fabric-grafana \| grep -i plugin` |
| `Base dashboard has no panel titled '__WEATHERMAP_SLOT__'` | Someone edited `dashboard-base.json` and renamed/removed that panel | Check panel `id: 1` still has that exact title |
| `HTTP 401/403` fetching live positions | Expired/bad Grafana token | Re-issue the service account token |

## How it works

1. Read cEOS nodes and cEOS-to-cEOS links from `topology-data.json` (`ethN` renamed to
   `EtN`); links to Linux nodes are dropped, no gnmic counters there. Every link is 1G.
2. Position each node (see above).
3. Build the panel's PromQL `targets`: node status, per-side link tx (each side its own
   egress counter, so both directions are represented, #57), VXLAN MAC/VNI tooltip.
4. Build `nodes[]`/`links[]`, including the plugin's `anchors` tally (link count per
   side), required by the installed plugin fork (#48).
5. Cross-check every interface name against the live gnmic exporter (`Et` -> `Ethernet`);
   mismatches are logged, not dropped.
6. Load `dashboard-base.json`, substitute the datasource UID, splice the generated panel
   into `__WEATHERMAP_SLOT__` (keeping that slot's `gridPos`/`id`).
7. Write `fabric.json`; push it if `--provision`.

## Known gaps

- **VXLAN MAC-per-VNI tooltip**: the `vlan` join key doesn't match on live data for any
  VTEP node, likely an Arista internal-vs-front-panel VLAN translation gap. Only affects
  that one decorative tooltip metric, not node/link status or traffic coloring. Tracked
  in #44.

# scripts/generate_traffic.sh

Generates real DC↔Campus traffic over VRF `gold` using `iperf3` (bundled
in the `network-multitool` image every host container runs), with a live
bandwidth dashboard. Without this, host containers sit idle and ARP/MAC
tables, Grafana throughput graphs, and the weathermap panel stay
empty until someone manually generates traffic (see #55).

## Quickstart

```bash
./scripts/generate_traffic.sh <duration_seconds>
```

## How it works

- Starts `iperf3 -s` on the DC gold-VRF servers: `dc-server2`
  (10.34.34.102), `dc-server4` (10.78.78.104).
- Runs `iperf3 -c -R` from the paired campus gold-VRF hosts, reversing the
  stream so the DC server pushes to the campus consumer: `dc-server2` →
  `campus-host1`, `dc-server4` → `campus-host2` — exercising the full
  DC→Core→Campus stitched EVPN Type-5 path end to end.
- Redraws a terminal dashboard every second for the run duration: server
  list, and live Mbits/sec per client session parsed from `iperf3 -i 1`
  output.
- On exit (duration end or Ctrl-C), kills the client processes and stops
  the `iperf3 -s` processes on the DC servers — no leftover state.

`dc-server1`/`dc-server3` (VLAN 40, VRF default, no gateway) are out of
scope — this script only exercises the routed gold VRF path.

# scripts/build_images.sh

Builds the local images referenced by `evpn-lab.clab.yml`; containerlab cannot build
images itself. Run it before `containerlab deploy`.

| Image                                   | Context                          | Why                                         |
| --------------------------------------- | -------------------------------- | ------------------------------------------- |
| `evpnlab/tac_plus-ng:latest`            | `images/tac_plus-ng/`            | TACACS+ server, no official image; pinned upstream commit (`TAC_PLUS_NG_REF`) |
| `evpnlab/network-multitool-8021x:latest` | `images/network-multitool-8021x/` | `network-multitool` + `wpa_supplicant` for `campus-host1` |

```bash
./scripts/build_images.sh          # builds missing images, skips existing ones
./scripts/build_images.sh --force  # rebuilds all (after a Dockerfile change)
```
