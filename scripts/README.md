# scripts/generate_weathermap.py

Generates a [weathermap-ng](https://github.com/allamiro/grafana-network-weathermap-ng)
**panel only** from live IPFabric topology + gnmic/Prometheus metrics, merges
it into a manually-authored dashboard base, and writes the merged result to
`configs/grafana/weathermap-dashboard.json` (committed to Gitea as the build
artifact, same pattern as the retired Flow Panel YAML). Optionally provisions
it into Grafana via the HTTP API.

## File structure (see #52)

| File | What it is |
|---|---|
| `configs/grafana/dashboard-base.json` | **Manually authored**, committed source of truth for everything except the weathermap panel: BGP sessions table, ports/interfaces table, throughput-per-site graphs, `site`/`device` template variables, panel layout. Edit this directly for anything in those panels. Contains a reserved slot panel titled `__WEATHERMAP_SLOT__` (id `1`, `gridPos` fixed) that the script splices the generated weathermap panel into. |
| `configs/grafana/weathermap-dashboard.json` | **Generated build artifact** — base + freshly-generated weathermap panel, merged. This is what actually gets provisioned to Grafana. Don't hand-edit; re-run the script. |

The script itself only ever knows about the weathermap panel (`targets` +
`options.weathermap`) — it has no knowledge of the other three panels or the
template variables. That split is deliberate: topology-driven content
(nodes/links, generated from live IPFabric+Prometheus data) is separated from
hand-tuned dashboard composition (table layout, transformations, thresholds),
which doesn't need to regenerate on every topology change.

See issue #48 for the panel schema research this is built against, and its
comment thread for the live-validation history (auth quirks, plugin id, a
PromQL escaping bug, a panel-crash fix — worth reading before touching the
anchor/regex-escaping logic).

## Usage

```bash
export IPFABRIC_URL=https://<ipfabric-instance>
export IPFABRIC_TOKEN=<token>
python3 scripts/generate_weathermap.py                 # writes the merged JSON only

export GRAFANA_URL=https://<external-grafana-instance>
export GRAFANA_TOKEN=<token>
export GRAFANA_DATASOURCE_UID=<prometheus-datasource-uid-in-grafana>
python3 scripts/generate_weathermap.py --provision      # also provisions via the Grafana API
```

Re-run after any topology change (`evpn-lab.clab.yml`) to regenerate the
weathermap panel and re-merge/re-provision. The script always regenerates the
weathermap panel fresh from live IPFabric data (no diffing/incremental
state), so a plain re-run already picks up any topology change — there's no
separate "detect changes" step. The only manual/operational step is
*triggering* that re-run after a change; there's no watcher or CI hook doing
it automatically yet.

If you need to change the BGP/ports/throughput panels, template variables, or
layout, edit `configs/grafana/dashboard-base.json` directly and re-run the
script (or run it with `--provision` to push the edit live) — no topology
data is needed for that path, the weathermap panel just gets regenerated
alongside it.

## Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `--base` (CLI flag, not env) | no | `configs/grafana/dashboard-base.json` | Manual dashboard base to merge the weathermap panel into. |
| `IPFABRIC_URL` | yes | — | e.g. `https://ipfabric.example.com` |
| `IPFABRIC_TOKEN` | yes | — | Inventory/Snapshots read access. Sent as `X-API-Token`, not `Authorization: Bearer` — IPFabric's REST API does not use bearer auth. |
| `IPFABRIC_SNAPSHOT` | no | `$last` | |
| `PROMETHEUS_URL` | no | `http://172.16.0.71:9090` | The **in-topology** Prometheus (see #45), used at generation time to validate the IPFabric→gnmic interface alias and to discover live VTEP/VLAN pairs. This does not have to be the same instance Grafana queries at render time — see below. |
| `GRAFANA_URL` | no (see #53) | — | Required for `--provision`. Also used, if set, to fetch the currently-provisioned dashboard and preserve any manually drag-and-drop-repositioned node positions — see step 3 below. Without it, every node gets the layered default position, even ones a human previously repositioned in the UI. |
| `GRAFANA_TOKEN` | no (see #53) | — | Grafana Service Account token, sent as `Authorization: Bearer`. Same conditions as `GRAFANA_URL` above. |
| `GRAFANA_DATASOURCE_UID` | with `--provision` | — | UID of the Prometheus datasource in Grafana that will actually back the panel. **This must be a datasource that can see the gnmic metrics** — an unrelated/external Prometheus instance with no gnmic data will make the panel render with no values (this happened once, see #48). |
| `GRAFANA_DASHBOARD_UID` | no | `evpn-vxlan-fabric-weathermap` | |
| `GRAFANA_WEATHERMAP_PLUGIN_ID` | no | `tamirsuliman-weathermap-panel` | The installed weathermap-ng plugin id. Override if a different fork is installed — plugin ids don't always match the upstream repo name (the schema research in #48 was done against the `allamiro` fork's source; what's actually installed here is a different fork with a stricter/different runtime schema — see the `ANCHOR` handling in the script). |

## What the script does

1. Fetches device inventory + connectivity-matrix from IPFabric.
2. Filters the connectivity-matrix to physical Ethernet-to-Ethernet links
   only: drops Management-plane neighbor entries and `.100`/`.200`
   subinterface rows (802.1Q tags used for the gold VRF stitching on Core —
   they ride the same physical port as their parent interface and gnmic only
   exports physical interface counters), and dedupes the two directions
   IPFabric reports for each physical link into one.
3. Computes node positions (see #53):
   - **Default layered layout**, for nodes with no known position yet: role
     is parsed from the hostname naming convention (`*-spine*`→spine,
     `core*`→core, `*-border-leaf*`→border-leaf, `*-leaf*`→leaf,
     `*-access*`→access — same trust level as the `site` parsing used for
     the Prometheus relabel, not IPFabric-derived), giving Y-tiers top to
     bottom `spine → core → border-leaf → leaf → access`. X position is
     grouped/columned by site within each tier, so e.g. dc leafs and campus
     leafs land in the same row but different column bands. A hostname
     matching no role pattern is logged (not silently placed in the wrong
     tier) and put in a fallback tier below `access`.
   - **Live-position preservation**: position is edited by drag-and-drop
     directly in the Grafana UI, not in the git-committed base file — a
     deliberate exception to the "file is the only source of truth" rule
     from #52, because that's simply not where this field is edited. Before
     computing the default layout above, the script fetches the currently
     provisioned dashboard's weathermap panel (if `GRAFANA_URL`/`GRAFANA_TOKEN`
     are set) and reuses each existing node's live position as-is. Only
     genuinely new nodes (not in that live map — first-ever run, or a fresh
     device added to the topology) get the layered default. A device removed
     from the topology simply has no entry in this run's node/link output at
     all, so no orphaned position or dangling link reference is possible.
4. Builds the panel's `targets`: one PromQL query per metric family (BGP
   status, interface tx, interface rx, VXLAN MAC/VNI), each with an explicit
   `legendFormat` so the resolved display name is predictable.
5. Builds `nodes[]` and `links[]` referencing those resolved legend strings,
   including the plugin's `anchors` tally (per-node count of link
   attachments per side) and numeric anchor enum on each link side —
   omitting these crashes the panel on load in the installed plugin fork,
   despite the (fork-specific) schema research saying it's safe to skip.
6. Cross-checks every IPFabric interface name, aliased to gnmic's naming
   (`Et`→`Ethernet`, `Po`→`Port-Channel`, `Lo`→`Loopback`, `Vl`→`Vlan`,
   `Ma`→`Management`), against the live exporter. Any link whose aliased
   name has no matching series is logged, not silently dropped — the actual
   fix for a real mismatch belongs in gnmic interface aliasing (#43), not in
   this script.
7. Loads `configs/grafana/dashboard-base.json`, substitutes the real
   Prometheus datasource UID into its `__DATASOURCE_UID__` placeholders,
   finds the panel titled `__WEATHERMAP_SLOT__` and splices in the generated
   weathermap panel content (keeping the slot's `gridPos`/`id`, so the manual
   layout is never repositioned).
8. Writes the merged dashboard JSON to `configs/grafana/weathermap-dashboard.json`,
   and provisions it via `POST /api/dashboards/db` if `--provision` is passed.

## Known gaps

- **VXLAN MAC-per-VNI target**: the `vlan` join key used to correlate
  VLAN→VNI mapping with FDB entries (query verbatim from #44) doesn't
  actually match on live data for any VTEP node — likely an Arista
  internal-VLAN-vs-front-panel-VLAN translation the OpenConfig paths don't
  reconcile. Only affects the decorative per-VTEP tooltip metric, not
  node/link status or traffic coloring. Tracked in #44, not fixed here.
