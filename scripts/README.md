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

## How to generate and provision the dashboard, start to finish

This walks through the whole thing from nothing — no `weathermap-dashboard.json`,
no dashboard in Grafana — to a fully working, live-updating dashboard. Useful
for a first-ever setup, or after a full reset (deleting the generated JSON
and the Grafana dashboard, keeping `dashboard-base.json` — that file is the
hand-authored part of the project and is never deleted/regenerated).

### 1. Gather credentials

Four values are required; two more are worth setting so `--provision` works
without extra flags. Each has a fiddly API path and a much simpler UI path —
UI is recommended unless you're scripting this.

**IPFabric API token** (`IPFABRIC_TOKEN`)
- UI: IPFabric → user menu (top right) → **Settings** → **API Tokens** → **Add token**. Needs Inventory/Snapshots read access.
- No simpler API alternative — tokens can only be created through the UI or by an admin via the same UI.

**Grafana service account token** (`GRAFANA_TOKEN`)
- UI (recommended — the API path is multiple chained calls: create the service account, then create a token under it, threading the returned service account ID between them):
  1. Grafana → **Administration** → **Users and access** → **Service accounts** → **Add service account**.
  2. Give it a name (e.g. `weathermap-generator`), role **Editor** (needs to create/update dashboards).
  3. Open the new service account → **Add service account token** → copy the token immediately, it's shown once.

**Prometheus datasource UID** (`GRAFANA_DATASOURCE_UID`)
- UI: Grafana → **Connections** → **Data sources** → click the Prometheus datasource that can see the gnmic metrics (`NetLab` in this lab) → the UID is the last segment of the page URL (`.../datasources/edit/<uid>`).
- API alternative: `curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" "$GRAFANA_URL/api/datasources" | jq '.[] | {name, uid}'`
- **This must be a datasource that can actually see the gnmic metrics** — see the note in the Environment variables table below; picking the wrong one renders the panel with no data (happened once, see #48).

**Weathermap plugin ID** (`GRAFANA_WEATHERMAP_PLUGIN_ID`, optional — only if a different fork than `tamirsuliman-weathermap-panel` is installed)
- UI: Grafana → **Administration** → **Plugins and data** → **Plugins**, search "weathermap", open it — the id is in the page URL (`.../plugins/<id>`).
- API alternative: `curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" "$GRAFANA_URL/api/plugins?panelId=..." ` is more involved than it's worth; the UI is faster here.

**IPFabric/Grafana URLs** — just the base URLs you already use in a browser (e.g. `https://ipfabric.example.com`, `https://grafana.example.com`).

Copy `envrc.sample` to `.envrc` (already gitignored) and fill in the values,
or `export` them directly in your shell:

```bash
cp envrc.sample .envrc   # then edit .envrc
source .envrc
```

### 2. Dry run first (no Grafana changes yet)

```bash
python3 scripts/generate_weathermap.py
```

This only needs `IPFABRIC_URL`/`IPFABRIC_TOKEN` (and optionally `GRAFANA_URL`/`GRAFANA_TOKEN`,
to preserve any live node positions — see #53). It writes
`configs/grafana/weathermap-dashboard.json` and prints a summary:

```
Fetching devices from IPFabric (...)...
  28 devices
Fetching connectivity-matrix...
  61 fabric links after Management-plane filter + dedup (702 raw rows)
Fetching interface speeds...
Fetching live node positions from ... (preserve manual repositioning)...
  0 node(s) with an existing live position          <- 0 is expected/correct on a first-ever run
Cross-checking interface names against live exporter (...)...
Loading manual dashboard base (configs/grafana/dashboard-base.json)...
Wrote configs/grafana/weathermap-dashboard.json (28 nodes, 61 links, 4 panels total)
```

If any "interface-name / bandwidth mismatch(es)" are printed to stderr, read
them — they mean a link's query won't resolve to data until the underlying
gnmic/IPFabric naming mismatch is fixed (not this script's job to fix, see
"Known gaps" below), but the link itself is still generated, not dropped.

Open the written JSON and sanity-check it if you like before pushing it live
— it's plain, readable JSON, no need to trust it blindly.

### 3. Provision it

```bash
python3 scripts/generate_weathermap.py --provision
```

Requires `GRAFANA_URL`, `GRAFANA_TOKEN`, `GRAFANA_DATASOURCE_UID` in addition
to the IPFabric variables. On success:

```
Provisioning dashboard 'evpn-vxlan-fabric-weathermap' to https://...
  success: /d/evpn-vxlan-fabric-weathermap/evpn-vxlan-fabric-weathermap
```

### 4. Verify

**Via the UI (recommended, and the only way to actually see it render)**:
open `$GRAFANA_URL/d/evpn-vxlan-fabric-weathermap` in a browser. Check:
- The weathermap panel shows all nodes, roughly grouped spine-top/access-bottom (see #53), all colored green (up) with no data gaps.
- The `site`/`device` dropdown variables at the top of the dashboard filter the BGP Sessions and Ports/Interfaces tables when changed.
- BGP Sessions and Ports/Interfaces tables are populated, states colored (green=Up, red=Down).
- Throughput per Site shows a signed graph (in above the axis, out below) with plausible non-zero values.

This step has no good API substitute — dashboard rendering, panel colors,
and transformations (the ports table's Grafana-side merge, in particular)
only actually execute in a browser. If you don't have one handy, at minimum
confirm the queries resolve (below), then ask someone who does have UI
access to eyeball it.

**Via the API (queries only, not rendering)** — useful for CI/scripting or a
quick sanity check without opening a browser:

```bash
# Any panel's query, pulled straight from the generated JSON, e.g.:
curl -s -X POST -H "Authorization: Bearer $GRAFANA_TOKEN" -H "Content-Type: application/json" \
  "$GRAFANA_URL/api/ds/query" -d '{
    "queries": [{"refId":"A","datasource":{"type":"prometheus","uid":"'"$GRAFANA_DATASOURCE_UID"'"},
                 "expr":"min by (device) (interfaces_interface_state_oper_status)","instant":true}],
    "from":"now-5m","to":"now"}' | python3 -m json.tool
```

A much friendlier equivalent that doesn't need hand-built JSON: Grafana's
**Explore** view (left sidebar → **Explore**, pick the Prometheus datasource,
paste a PromQL expression from the panel JSON, run it). This is the manual
alternative for every `/api/ds/query` validation call used during
development of this dashboard (#49–#54) — same result, no `curl`/`jq`
required.

### 5. Re-running after a topology change

```bash
python3 scripts/generate_weathermap.py --provision
```

Same command — the script always regenerates the weathermap panel fresh from
live IPFabric data (no diffing/incremental state), so a plain re-run already
picks up any topology change. There's no separate "detect changes" step, and
no watcher/CI hook triggering it automatically yet — re-running after a
change is a manual/operational step for now.

Nodes you've manually repositioned in the Grafana UI keep that position
across the re-run (#53); only genuinely new nodes get the layered default.

If you only need to change the BGP/ports/throughput panels, template
variables, or panel layout, edit `configs/grafana/dashboard-base.json`
directly and re-run the script (or `--provision` to push it live) — no
topology fetch is skipped today (the script always does the full IPFabric
round-trip regardless), but no topology data is *needed* for that kind of
edit to take effect.

### Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| `Refusing to provision: set GRAFANA_DATASOURCE_UID...` | Env var unset or still the placeholder | `echo $GRAFANA_DATASOURCE_UID` |
| Panel loads but shows no data at all | Wrong datasource UID — points at a Prometheus instance that can't see the gnmic metrics | Grafana UI → Explore → run `up` against the datasource you set; confirm gnmic-labeled series come back |
| `Base dashboard has no panel titled '__WEATHERMAP_SLOT__'` | `dashboard-base.json` was edited and the slot panel's `title` got changed/removed | Check the panel with `id: 1` in `dashboard-base.json` still has that exact title |
| A node's manual position keeps resetting to the default layout on every rerun | `GRAFANA_URL`/`GRAFANA_TOKEN` not set for that run, so the live-position fetch was skipped entirely | Check the printed line `Fetching live node positions from ...` appears in the run's output — if it's missing, those two vars weren't set |
| `Fetching live dashboard for position preservation failed: HTTP 401/403` | Bad/expired Grafana token | Regenerate the service account token (UI steps above) |

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
