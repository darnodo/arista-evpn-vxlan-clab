#!/usr/bin/env python3
"""Generate a weathermap-ng PANEL (only) from the NetMapper topology + gnmic/Prometheus
metrics, merge it into a manually-authored dashboard base, and optionally
provision the result into Grafana.

Scope (see #52): this script knows only about the weathermap panel --
targets (node status / link tx per side / VXLAN tooltip queries) and
options.weathermap (nodes/links/scale/settings). It has no knowledge of the
BGP sessions table, ports/interfaces table, or throughput panels -- those
live in the manually-authored `configs/grafana/dashboard-base.json` and are
not touched by this script.

Data sources (see gitea issues #44, #47, #48, and #11):
  - NetMapper read API (docs/observability/netmapper.md): devices, LLDP links
    and port speeds from the latest crawl. Works the same against a production
    NetMapper, no containerlab file involved.
  - Prometheus (gnmic exporter, configs/prometheus/prometheus.yml): live label
    values, used both to validate the topology->gnmic interface names and to
    resolve which VTEPs/VLANs actually have VXLAN data.

Merge: the weathermap panel is generated fresh from live data on every run
(no diffing), then spliced into the base dashboard's reserved slot (the panel
titled "__WEATHERMAP_SLOT__"), keeping that slot's gridPos so the manually
authored layout is never repositioned by the generator. See #52.

Usage:
    uv run scripts/generate_weathermap.py [--base PATH] [--output PATH] [--allow-quarantined] [--provision]

The output is a plain dashboard JSON, provisioned from file by the in-lab
Grafana (configs/grafana/dashboards/). --provision also pushes it via the API.

Environment:
    NETMAPPER_URL        default http://172.16.0.82:8080 (in-topology instance)
    NETMAPPER_TOKEN      required, read-scope API token
    PROMETHEUS_URL       default http://172.16.0.71:9090 (in-topology instance)
    GRAFANA_URL           required with --provision
    GRAFANA_TOKEN     required with --provision
    GRAFANA_DATASOURCE_UID  Prometheus datasource UID in Grafana, default "prometheus"
        (UID provisioned in the in-lab Grafana)
    GRAFANA_DASHBOARD_UID  default "evpn-vxlan-fabric-weathermap"
    GRAFANA_WEATHERMAP_PLUGIN_ID  default "tamirsuliman-weathermap-panel" -- override
        if a different weathermap-ng fork/plugin id is installed.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse

WEATHERMAP_SCHEMA_VERSION = 14

# Weathermap links are physical data ports only: NetMapper also reports LLDP
# between Management ports (in the lab, across the docker mgmt bridge) and
# 802.1Q subinterfaces have no gnmic counters of their own.
DATA_PORT = re.compile(r"^Ethernet[\d/]+$")

SITE_ORDER = ["dc", "core", "campus"]
GRID_COLUMNS = 6
GRID_SPACING_X = 180
GRID_SPACING_Y = 150

# Layered default layout (see #53): device role is parsed from the hostname
# naming convention, same trust level as the `site` parsing already in place
# for the Prometheus relabel (#49) -- not topology-derived, not configurable.
# Checked in this order so e.g. "campus-border-leaf1" matches border-leaf
# before the more general leaf pattern.
ROLE_PATTERNS = [
    ("spine", re.compile(r"-spine")),
    ("core", re.compile(r"^core")),
    ("border-leaf", re.compile(r"-border-leaf")),
    ("leaf", re.compile(r"-leaf")),
    ("access", re.compile(r"-access")),
]
ROLE_TIER_ORDER = ["spine", "core", "border-leaf", "leaf", "access"]
TIER_SPACING_Y = 300
# Per-site X band start, wide enough that the largest role/site group (8 dc
# leafs) doesn't spill into the next site's band at GRID_COLUMNS=6.
SITE_X_OFFSET = {"dc": 100, "core": 1300, "campus": 1600}
UNMATCHED_ROLE_TIER_Y = len(ROLE_TIER_ORDER) * TIER_SPACING_Y + 300

# tamirsuliman-weathermap-panel's numeric anchor enum (Center=0, Top=1,
# Bottom=2, Left=3, Right=4) -- reverse-engineered from module.js, since
# link.sides.*.anchor and node.anchors{} both index by this numeric value,
# not by the anchor name string.
ANCHOR = {"Center": 0, "Top": 1, "Bottom": 2, "Left": 3, "Right": 4}

NODE_COLORS = {"font": "#ffffff", "background": "#22252b", "border": "#5794F2", "statusDown": "#F2495C"}
STATUS_VALUE_MAPPINGS = [{"value": 0, "color": "#F2495C"}, {"value": 1, "color": "#73BF69"}]
# Used only when NetMapper knows neither port's speed (logged as a mismatch).
FALLBACK_LINK_BANDWIDTH_BPS = 1_000_000_000


def env(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"Missing required environment variable: {name}")
    return val


# --------------------------------------------------------------------------
# NetMapper topology (see #11)
# --------------------------------------------------------------------------

def netmapper_get(base_url, token, path, params=None):
    url = f"{base_url.rstrip('/')}/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 401:
            sys.exit("NetMapper API refused the token (HTTP 401): check NETMAPPER_TOKEN")
        if e.code == 409 and "not_projected" in body:
            sys.exit("NetMapper has no graph yet: run a crawl first (lab: ./scripts/netmapper_setup.sh)")
        sys.exit(f"NetMapper API /v1/{path}: HTTP {e.code} {body}")
    except urllib.error.URLError as e:
        sys.exit(f"NetMapper API unreachable at {base_url}: {e.reason}")


def short_hostname(fqdn):
    """NetMapper reports the device's FQDN (dc-leaf1.evpnlab.local); gnmic's
    `device` label and the naming convention use the short name."""
    return fqdn.split(".")[0]


def parse_port_ref(ref, hosts):
    """(hostname, port) for an edge end "if:<device_key>/<port>" on a crawled
    device and a physical data port, else None (Management port, far end
    NetMapper could not resolve, ...). The port may itself contain "/"
    (Ethernet1/1), the device key never does."""
    if not ref.startswith("if:"):
        return None
    key, port = ref[3:].split("/", 1)
    if key not in hosts or not DATA_PORT.match(port):
        return None
    return hosts[key], port


def load_netmapper_topology(base_url, token, allow_quarantined, mismatches):
    """Devices and physical links of the latest NetMapper graph. Every call
    after the first is pinned to the same snapshot, so a crawl finishing
    mid-run cannot mix two graphs. NetMapper names a cable once whichever end
    reports it, so links come out deduplicated, with the port speed read from
    the device."""
    listing = netmapper_get(base_url, token, "devices")
    snapshot = listing["snapshot"]
    print(f"  snapshot {snapshot['id']} closed {snapshot['closed_at']}, verdict {snapshot['verdict']}")
    if snapshot["verdict"] == "quarantined" and not allow_quarantined:
        sys.exit(f"Snapshot {snapshot['id']} is quarantined (the crawl reached much less than the previous one): "
                 f"refusing to rebuild the map from it, pass --allow-quarantined to override")
    pin = {"snapshot": snapshot["id"]}

    hosts = {}  # device_key -> short hostname
    for dev in listing["devices"]:
        if not dev["hostname"]:
            mismatches.append(f"device {dev['device_key']} has no hostname in NetMapper, left off the map")
            continue
        hosts[dev["device_key"]] = short_hostname(dev["hostname"])
    devices = []
    for host in sorted(hosts.values()):
        site = re.match(r"(campus|core|dc)", host)
        devices.append({"hostname": host, "siteName": site.group(1) if site else "unknown"})

    speeds = {}  # edge end ref -> speed_bps (None when the device did not report it)
    edges = {}   # edge name -> edge; each cable is listed by the devices at both ends
    for key in hosts:
        detail = netmapper_get(base_url, token, f"devices/{urllib.parse.quote(key, safe='')}", pin)
        for iface in detail["interfaces"]:
            speeds[f"if:{key}/{iface['canonical_name']}"] = iface["speed_bps"]
        for edge in detail["edges"]:
            if edge["type"] == "l1_link":
                edges[edge["name"]] = edge

    links = []
    for edge in edges.values():
        a = parse_port_ref(edge["from_ref"], hosts)
        z = parse_port_ref(edge["to_ref"], hosts)
        if a is None or z is None:
            continue
        (a_host, a_int), (z_host, z_int) = sorted([a, z])
        # Both ends of a cable run at the same speed; take whichever is known.
        bandwidth = speeds.get(edge["from_ref"]) or speeds.get(edge["to_ref"])
        if not bandwidth:
            mismatches.append(f"{a_host} {a_int} <-> {z_host} {z_int}: no port speed in NetMapper, "
                              f"assuming {FALLBACK_LINK_BANDWIDTH_BPS} bps")
            bandwidth = FALLBACK_LINK_BANDWIDTH_BPS
        links.append({"a_host": a_host, "a_int": a_int, "z_host": z_host, "z_int": z_int, "bandwidth": bandwidth})
    # Sorted by name, not by edge name: that holds the device key (chassis MAC),
    # which a cEOS redeploy changes, and the output file would churn in git.
    links.sort(key=lambda link: (link["a_host"], link["a_int"], link["z_host"], link["z_int"]))
    return devices, links


# --------------------------------------------------------------------------
# Prometheus (validation + VXLAN discovery)
# --------------------------------------------------------------------------

def prom_query(prometheus_url, promql):
    url = f"{prometheus_url.rstrip('/')}/api/v1/query?query=" + urllib.parse.quote(promql)
    with urllib.request.urlopen(url, timeout=15) as resp:
        payload = json.load(resp)
    if payload["status"] != "success":
        sys.exit(f"Prometheus query failed: {promql}")
    return payload["data"]["result"]


def known_interface_pairs(prometheus_url):
    """(device, interface) pairs that actually exist in the gnmic exporter,
    used to check the NetMapper hostname/port names before trusting them."""
    results = prom_query(prometheus_url, "interfaces_interface_state_oper_status")
    return {(m["metric"]["device"], m["metric"]["interface"]) for m in results}


def known_vtep_vlan_pairs(prometheus_url):
    """(device, vlan) pairs with a live VLAN-to-VNI mapping -- these are the
    VTEP nodes eligible for a VXLAN MAC-count tooltip metric."""
    results = prom_query(prometheus_url, "interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni")
    return {(m["metric"]["device"], m["metric"]["vlan"]) for m in results}


def promql_escape(s):
    """re.escape() escapes '-' as '\\-', which Python's own regex engine
    accepts but PromQL's RE2-based engine rejects ("unknown escape sequence
    U+002D '-'") -- and every hostname in this lab contains hyphens. '-' is
    not a regex metacharacter outside a character class, so it's safe to
    leave unescaped."""
    return re.escape(s).replace("\\-", "-")


# --------------------------------------------------------------------------
# Topology processing
# --------------------------------------------------------------------------

def parse_role(hostname):
    """Device role from the hostname naming convention -- see ROLE_PATTERNS.
    Returns None if nothing matches (logged by the caller, not silently
    defaulted into the wrong tier)."""
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(hostname):
            return role
    return None


def build_layout(devices, mismatches):
    """Default layered layout for nodes with no live (Grafana-drag-and-drop)
    position yet -- see #53. Y-tier by role (spine top, access bottom), X
    grouped/columned by site within each tier so same-role devices from
    different sites don't overlap."""
    groups = {}  # (role, site) -> [hostname, ...]
    unmatched = []
    for dev in devices:
        host, site = dev["hostname"], dev["siteName"]
        role = parse_role(host)
        if role is None:
            unmatched.append(host)
            continue
        groups.setdefault((role, site), []).append(host)

    positions = {}
    for role_idx, role in enumerate(ROLE_TIER_ORDER):
        tier_y = role_idx * TIER_SPACING_Y
        for site in SITE_ORDER:
            x_offset = SITE_X_OFFSET.get(site, max(SITE_X_OFFSET.values()) + 300)
            for idx, host in enumerate(sorted(groups.get((role, site), []))):
                col, row = idx % GRID_COLUMNS, idx // GRID_COLUMNS
                positions[host] = [x_offset + col * GRID_SPACING_X, tier_y + row * GRID_SPACING_Y]

    if unmatched:
        mismatches.append(
            f"{len(unmatched)} hostname(s) matched no role pattern (spine/core/border-leaf/leaf/access), "
            f"placed in a fallback tier instead of guessing: {', '.join(sorted(unmatched))}"
        )
        for idx, host in enumerate(sorted(unmatched)):
            col, row = idx % GRID_COLUMNS, idx // GRID_COLUMNS
            positions[host] = [100 + col * GRID_SPACING_X, UNMATCHED_ROLE_TIER_Y + row * GRID_SPACING_Y]

    return positions


# --------------------------------------------------------------------------
# Weathermap assembly
# --------------------------------------------------------------------------

def build_weathermap(devices, links, positions, prometheus_url, mismatches):
    hostnames = [d["hostname"] for d in devices]
    host_regex = "|".join(promql_escape(h) for h in hostnames)

    known_pairs = known_interface_pairs(prometheus_url)
    vtep_vlan_pairs = known_vtep_vlan_pairs(prometheus_url)
    vtep_hosts = sorted({dev for dev, _ in vtep_vlan_pairs})

    def check_interface(host, interface, side_label):
        """NetMapper and gnmic both use the full EOS port name (Ethernet1), and
        the hostname is shortened on load; anything still not matching is a
        device gnmic doesn't subscribe to, or a naming gap to fix."""
        if (host, interface) not in known_pairs:
            mismatches.append(
                f"{host} {interface} ({side_label}): no matching series in "
                f"interfaces_interface_state_oper_status -- link will reference a query that "
                f"resolves to no data until gnmic covers this device/port"
            )

    # -- nodes --
    # anchors{} tallies how many link-sides attach to each anchor position on
    # this node; every link below uses Right for its A side and Left for its
    # Z side, so that's what gets counted per node here.
    anchor_counts = {host: {a: 0 for a in ANCHOR.values()} for host in (d["hostname"] for d in devices)}
    for link in links:
        anchor_counts[link["a_host"]][ANCHOR["Right"]] += 1
        anchor_counts[link["z_host"]][ANCHOR["Left"]] += 1

    nodes = []
    for dev in devices:
        host = dev["hostname"]
        node = {
            "id": host,
            "label": host,
            "position": positions[host],
            "isConnection": False,
            "useConstantSpacing": False,
            # True (not the plugin default) so rendered node HEIGHT is
            # constant, decoupled from per-node link count -- see #54. Ground
            # truth confirmed against the installed plugin's real module.js
            # (not the #48 schema doc, which doesn't cover this): height is
            # `fontSize + 2*padding.vertical` when compactVerticalLinks is
            # true, unconditionally; when false, it's the larger of that or
            # a term proportional to max(anchors[Left].numLinks,
            # anchors[Right].numLinks) -- exactly why campus-leaf1 (3 links)
            # and campus-leaf2 (4 links) rendered at different heights.
            # Width is unaffected either way: it's always recomputed from
            # the label text at render time (no override field exists), and
            # useConstantSpacing only pulls in Top/Bottom anchor link count,
            # which this generator never uses (links always attach
            # Right/Left -- see anchor_counts above).
            "compactVerticalLinks": True,
            "padding": {"horizontal": 12, "vertical": 6},
            "colors": dict(NODE_COLORS),
            "nodeIcon": None,
            "statusQuery": f"STATUS {host}",
            "nodeStatusColorTarget": "border",
            "statusValueMappings": [dict(m) for m in STATUS_VALUE_MAPPINGS],
            "anchors": {a: {"numLinks": anchor_counts[host][a], "numFilledLinks": 0} for a in ANCHOR.values()},
        }
        if host in vtep_hosts:
            node["tooltipMetrics"] = [
                {"label": f"VNI {host} {vlan}", "query": f"VNI {host} {vlan}", "units": "MACs"}
                for _, vlan in sorted(v for v in vtep_vlan_pairs if v[0] == host)
            ]
        nodes.append(node)

    # -- links --
    link_defs = []
    interface_regex_parts = set()
    for link in links:
        a_int, z_int = link["a_int"], link["z_int"]
        check_interface(link["a_host"], a_int, "side A")
        check_interface(link["z_host"], z_int, "side Z")
        interface_regex_parts.add(promql_escape(a_int))
        interface_regex_parts.add(promql_escape(z_int))

        link_defs.append({
            "id": f"{link['a_host']}-{a_int}--{link['z_host']}-{z_int}",
            "nodes": [{"id": link["a_host"]}, {"id": link["z_host"]}],
            # Each side's query is that side's own tx (egress) counter, not the
            # far end's rx -- see #57. a_host tx and z_host rx both describe the
            # *same* A->Z flow measured from opposite ends (the a_host->z_host
            # direction, counted twice), leaving the Z->A direction never
            # queried by either side. Using each node's own tx gives two
            # independent, opposite-direction measurements instead.
            "sides": {
                "A": {
                    "bandwidth": link["bandwidth"],
                    "query": f"{link['a_host']} {a_int} tx",
                    "labelOffset": 55, "anchor": ANCHOR["Right"], "dashboardLink": "",
                },
                "Z": {
                    "bandwidth": link["bandwidth"],
                    "query": f"{link['z_host']} {z_int} tx",
                    "labelOffset": 55, "anchor": ANCHOR["Left"], "dashboardLink": "",
                },
            },
            "units": "bps",
            "arrows": {"width": 8, "height": 10, "offset": 2},
            "stroke": 5,
            "showThroughputPercentage": False,
        })

    interface_regex = "|".join(sorted(interface_regex_parts))

    # -- targets (one query per metric family, per task spec) --
    #
    # Node status (refId A): a device is "up" only if at least one interface
    # is up AND every BGP session is up, if it has any -- see #49. The old
    # "BGP {{device}}" query sourced raw per-neighbor session-state series,
    # so a device with multiple neighbors collided on one legend string and
    # only one arbitrarily won. `min by (device)` picks the *worst* session
    # (0 beats 1), and devices with zero BGP sessions (access switches) are
    # not penalized: the `or` fallback substitutes a constant 1 for any
    # device present in device-up but absent from the BGP series entirely.
    device_up = f'min by (device) (interfaces_interface_state_oper_status{{device=~"{host_regex}"}})'
    bgp_worst = (
        f'min by (device) (network_instances_network_instance_protocols_protocol_bgp_neighbors_neighbor_state_session_state'
        f'{{network_instance_name="default", device=~"{host_regex}"}})'
    )
    bgp_ok_or_not_applicable = f'({bgp_worst} or ({device_up} * 0 + 1))'
    targets = [
        {
            "refId": "A",
            "expr": f'{device_up} * {bgp_ok_or_not_applicable}',
            "legendFormat": "STATUS {{device}}",
        },
        {
            "refId": "B",
            "expr": f'rate(interfaces_interface_state_counters_out_octets{{device=~"{host_regex}", interface=~"{interface_regex}"}}[5m]) * 8',
            "legendFormat": "{{device}} {{interface}} tx",
        },
    ]
    if vtep_hosts:
        vtep_regex = "|".join(promql_escape(h) for h in vtep_hosts)
        # Verbatim join from #44 "VXLAN (MAC count per VNI)", scoped to VTEP nodes.
        # RHS is wrapped in max by (device, vlan) so the join key is always
        # unique -- a Prometheus restart or relabel change otherwise leaves
        # the pre-restart (frozen) and post-restart series briefly coexisting
        # within the 5m staleness window, both matching the same (device,
        # vlan) group, which trips PromQL's "many-to-many matching not
        # allowed" error. See #50.
        targets.append({
            "refId": "D",
            "expr": (
                f'count by (device, vlan) (network_instances_network_instance_fdb_mac_table_entries_entry_vlan{{device=~"{vtep_regex}"}})\n'
                f'* on(device, vlan) group_left(vlan_to_vni_state_vni)\n'
                f'max by (device, vlan) (interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni{{device=~"{vtep_regex}"}})'
            ),
            "legendFormat": "VNI {{device}} {{vlan}}",
        })

    weathermap = {
        "version": WEATHERMAP_SCHEMA_VERSION,
        "id": "evpn-vxlan-fabric-weathermap",
        "nodes": nodes,
        "links": link_defs,
        "scale": [
            {"percent": 0, "color": "#5794F2"},
            {"percent": 70, "color": "#FA6400"},
            {"percent": 90, "color": "#C4162A"},
        ],
        "settings": {
            "panel": {"backgroundColor": "#212124", "panelSize": {"width": 1600, "height": 1000},
                      "zoomScale": 0, "offset": {"x": 0, "y": 0}, "showTimestamp": True,
                      "grid": {"enabled": False, "size": 10, "guidesEnabled": False}},
            "link": {"spacing": {"horizontal": 10, "vertical": 5}, "stroke": {"color": "#CCCCDC"},
                     "label": {"background": "#FFFFFF", "border": "#000000", "font": "#000000"},
                     "showAllWithPercentage": False, "defaultUnits": "bps"},
            "tooltip": {"fontSize": 10, "textColor": "#CCCCDC", "backgroundColor": "#1A1B1F",
                        "inboundColor": "#73BF69", "outboundColor": "#5794F2", "scaleToBandwidth": False},
            "fontSizing": {"node": 12, "link": 10},
            "scale": {"position": {"x": 0, "y": 0}, "size": {"width": 150, "height": 100},
                      "title": "Utilization", "fontSizing": {"title": 10, "threshold": 9}},
        },
    }
    return weathermap, targets


# --------------------------------------------------------------------------
# Weathermap panel (only) -- see #52, scope narrowed from full-dashboard
# --------------------------------------------------------------------------

WEATHERMAP_SLOT_TITLE = "__WEATHERMAP_SLOT__"
WEATHERMAP_PANEL_TITLE = "Fabric Weathermap"  # what the slot is renamed to on merge


def build_weathermap_panel(weathermap, targets, datasource_uid, plugin_id):
    """The weathermap panel's own content: type/datasource/targets/options.
    Deliberately has no gridPos/id/title of its own -- those come from
    whatever slot it's merged into (see merge_weathermap_into_base)."""
    return {
        "type": plugin_id,
        "datasource": {"type": "prometheus", "uid": datasource_uid},
        "targets": [dict(t, datasource={"type": "prometheus", "uid": datasource_uid}) for t in targets],
        "options": {"weathermap": weathermap},
    }


# --------------------------------------------------------------------------
# Manual base dashboard + merge (see #52)
# --------------------------------------------------------------------------

def load_base_dashboard(path):
    with open(path) as f:
        return json.load(f)


def substitute_placeholders(obj, replacements):
    """Recursively replace exact-match string placeholders (e.g. the
    datasource UID token) anywhere in the manually-authored base JSON."""
    if isinstance(obj, dict):
        return {k: substitute_placeholders(v, replacements) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_placeholders(v, replacements) for v in obj]
    if isinstance(obj, str) and obj in replacements:
        return replacements[obj]
    return obj


def merge_weathermap_into_base(base_dashboard, weathermap_panel, dashboard_uid):
    """Splice the freshly generated weathermap panel into the base
    dashboard's reserved slot (matched by title), keeping the slot's
    gridPos/id -- layout stays manual, the generator never repositions it."""
    dashboard = dict(base_dashboard)
    dashboard["uid"] = dashboard_uid
    panels = []
    found = False
    for panel in dashboard.get("panels", []):
        if panel.get("title") == WEATHERMAP_SLOT_TITLE:
            found = True
            merged = dict(panel)
            merged.update(weathermap_panel)
            merged["title"] = WEATHERMAP_PANEL_TITLE
            panels.append(merged)
        else:
            panels.append(panel)
    if not found:
        sys.exit(f"Base dashboard has no panel titled {WEATHERMAP_SLOT_TITLE!r} -- nowhere to merge the weathermap panel")
    dashboard["panels"] = panels
    return dashboard


def fetch_live_node_positions(grafana_url, api_token, dashboard_uid):
    """Node positions as currently provisioned in Grafana, keyed by node id
    -- see #53. Position is edited live via drag-and-drop in the Grafana UI,
    not in the git-committed base file, so it's the one weathermap field that
    must be sourced from live Grafana state rather than regenerated or read
    from the manual base -- a manual repositioning must survive every rerun.

    Returns {} if the dashboard doesn't exist yet (first-ever run) or has no
    weathermap panel yet -- everything falls back to the default layered
    layout in that case. Any other HTTP error is treated as a real
    misconfiguration (e.g. a bad token) and raised, rather than silently
    treated as "no dashboard" -- that would risk quietly discarding every
    manual position on a run that should have failed loudly instead."""
    req = urllib.request.Request(
        f"{grafana_url.rstrip('/')}/api/dashboards/uid/{dashboard_uid}",
        headers={"Authorization": f"Bearer {api_token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        sys.exit(f"Fetching live dashboard for position preservation failed: HTTP {e.code} {e.read().decode()}")

    for panel in payload.get("dashboard", {}).get("panels", []):
        if panel.get("title") == WEATHERMAP_PANEL_TITLE:
            nodes = panel.get("options", {}).get("weathermap", {}).get("nodes", [])
            return {n["id"]: n["position"] for n in nodes if "position" in n}
    return {}


def load_file_node_positions(path):
    """Node positions from a previously generated dashboard file (the committed
    configs/grafana/dashboards/fabric.json), keyed by node id. Used when no live
    Grafana is queried, so positions tuned once and committed survive a rerun.
    Accepts both the plain dashboard and the older {"dashboard": ...} API payload."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    for panel in data.get("dashboard", data).get("panels", []):
        if panel.get("title") == WEATHERMAP_PANEL_TITLE:
            nodes = panel.get("options", {}).get("weathermap", {}).get("nodes", [])
            return {n["id"]: n["position"] for n in nodes if "position" in n}
    return {}


def provision_to_grafana(grafana_url, api_token, dashboard_payload):
    req = urllib.request.Request(
        f"{grafana_url.rstrip('/')}/api/dashboards/db",
        data=json.dumps(dashboard_payload).encode(),
        headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"Grafana provisioning failed: HTTP {e.code} {e.read().decode()}")


# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="configs/grafana/dashboard-base.json",
                         help="manually-authored dashboard base JSON (everything but the weathermap panel)")
    parser.add_argument("--output", default="configs/grafana/dashboards/fabric.json",
                         help="where to write the merged dashboard JSON (provisioned from file by the in-lab Grafana)")
    parser.add_argument("--allow-quarantined", action="store_true",
                         help="build the map even if NetMapper quarantined the latest crawl (reached much less than before)")
    parser.add_argument("--provision", action="store_true",
                         help="also POST the merged dashboard to the Grafana API (requires GRAFANA_* env vars)")
    args = parser.parse_args()

    netmapper_url = env("NETMAPPER_URL", "http://172.16.0.82:8080")
    netmapper_token = env("NETMAPPER_TOKEN", required=True)
    prometheus_url = env("PROMETHEUS_URL", "http://172.16.0.71:9090")
    dashboard_uid = env("GRAFANA_DASHBOARD_UID", "evpn-vxlan-fabric-weathermap")
    datasource_uid = env("GRAFANA_DATASOURCE_UID", "prometheus")
    plugin_id = env("GRAFANA_WEATHERMAP_PLUGIN_ID", "tamirsuliman-weathermap-panel")
    grafana_url = env("GRAFANA_URL")
    grafana_token = env("GRAFANA_TOKEN")

    mismatches = []
    print(f"Reading topology from NetMapper ({netmapper_url})...")
    devices, links = load_netmapper_topology(netmapper_url, netmapper_token, args.allow_quarantined, mismatches)
    print(f"  {len(devices)} devices, {len(links)} physical links")

    default_positions = build_layout(devices, mismatches)

    # Position specifically is edited live in the Grafana UI (drag-and-drop),
    # not in the git-committed base file -- see #53. Reuse whatever's live
    # for nodes that already exist there; only brand-new nodes get the
    # layered default. Iterating over default_positions (this run's device
    # set) rather than the live map means a removed device's stale live
    # position is simply never looked up again, no orphaned entry survives.
    if grafana_url and grafana_token:
        print(f"Fetching live node positions from {grafana_url} (preserve manual repositioning)...")
        live_positions = fetch_live_node_positions(grafana_url, grafana_token, dashboard_uid)
        print(f"  {len(live_positions)} node(s) with an existing live position")
    else:
        print(f"GRAFANA_URL/GRAFANA_TOKEN not set -- reusing node positions from {args.output} if present", file=sys.stderr)
        live_positions = load_file_node_positions(args.output)
        print(f"  {len(live_positions)} node(s) with an existing position in the file")
    positions = {host: live_positions.get(host, default) for host, default in default_positions.items()}

    print(f"Cross-checking interface names against live exporter ({prometheus_url})...")
    weathermap, targets = build_weathermap(devices, links, positions, prometheus_url, mismatches)

    if mismatches:
        print(f"\n{len(mismatches)} mismatch(es) found (link/position kept, not dropped):", file=sys.stderr)
        for m in mismatches:
            print(f"  - {m}", file=sys.stderr)
        print(file=sys.stderr)

    weathermap_panel = build_weathermap_panel(weathermap, targets, datasource_uid, plugin_id)

    print(f"Loading manual dashboard base ({args.base})...")
    base_dashboard = load_base_dashboard(args.base)
    base_dashboard = substitute_placeholders(base_dashboard, {"__DATASOURCE_UID__": datasource_uid})
    dashboard = merge_weathermap_into_base(base_dashboard, weathermap_panel, dashboard_uid)

    # Plain dashboard JSON: what Grafana file provisioning expects
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(dashboard, f, indent=2)
        f.write("\n")
    print(f"Wrote {args.output} ({len(weathermap['nodes'])} nodes, {len(weathermap['links'])} links, "
          f"{len(dashboard['panels'])} panels total)")

    if args.provision:
        if not (grafana_url and grafana_token):
            sys.exit("Refusing to provision: GRAFANA_URL and GRAFANA_TOKEN must both be set")
        print(f"Provisioning dashboard '{dashboard_uid}' to {grafana_url}...")
        result = provision_to_grafana(grafana_url, grafana_token, {"dashboard": dashboard, "overwrite": True})
        print(f"  {result.get('status')}: {result.get('url')}")


if __name__ == "__main__":
    main()
