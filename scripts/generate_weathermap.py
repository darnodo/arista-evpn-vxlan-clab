#!/usr/bin/env python3
"""Generate a weathermap-ng panel config from IPFabric topology + gnmic/Prometheus
metrics, and optionally provision it into a Grafana dashboard.

Data sources (see gitea issues #44, #47, #48):
  - IPFabric REST API: device inventory + connectivity-matrix (topology)
  - Prometheus (gnmic exporter, configs/prometheus/prometheus.yml): live label
    values, used both to validate the IPFabric->gnmic interface-name mapping
    and to resolve which VTEPs/VLANs actually have VXLAN data.

Usage:
    python3 scripts/generate_weathermap.py [--output PATH] [--provision]

Environment:
    IPFABRIC_URL        e.g. https://ipfabric.example.com
    IPFABRIC_TOKEN       API token (Inventory/Snapshots read access)
    IPFABRIC_SNAPSHOT    snapshot id, default "$last"
    PROMETHEUS_URL       default http://172.16.0.71:9090 (in-topology instance)
    GRAFANA_URL           required with --provision
    GRAFANA_TOKEN     required with --provision
    GRAFANA_DATASOURCE_UID  Prometheus datasource UID in Grafana, required with --provision
    GRAFANA_DASHBOARD_UID  default "evpn-vxlan-fabric-weathermap"
    GRAFANA_WEATHERMAP_PLUGIN_ID  default "allamiro-weathermap-panel" -- confirm
        against the actually installed plugin id before provisioning.
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

# IPFabric abbreviated interface prefixes -> gnmic/OpenConfig full names.
# Longest-prefix-first so e.g. "Ma" doesn't shadow a hypothetical multi-letter clash.
INTERFACE_PREFIX_ALIASES = {
    "Et": "Ethernet",
    "Po": "Port-Channel",
    "Lo": "Loopback",
    "Vl": "Vlan",
    "Ma": "Management",
}

SITE_ORDER = ["dc", "core", "campus"]
GRID_COLUMNS = 6
GRID_SPACING_X = 180
GRID_SPACING_Y = 150
SITE_BAND_Y = {"dc": 0, "core": 450, "campus": 750}

# tamirsuliman-weathermap-panel's numeric anchor enum (Center=0, Top=1,
# Bottom=2, Left=3, Right=4) -- reverse-engineered from module.js, since
# link.sides.*.anchor and node.anchors{} both index by this numeric value,
# not by the anchor name string.
ANCHOR = {"Center": 0, "Top": 1, "Bottom": 2, "Left": 3, "Right": 4}

NODE_COLORS = {"font": "#ffffff", "background": "#22252b", "border": "#5794F2", "statusDown": "#F2495C"}
STATUS_VALUE_MAPPINGS = [{"value": 0, "color": "#F2495C"}, {"value": 1, "color": "#73BF69"}]
DEFAULT_LINK_BANDWIDTH_BPS = 10_000_000_000  # 10G fallback when IPFabric speed is missing


def env(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and not val:
        sys.exit(f"Missing required environment variable: {name}")
    return val


# --------------------------------------------------------------------------
# IPFabric
# --------------------------------------------------------------------------

def ipfabric_request(base_url, token, path, body):
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api{path}",
        data=json.dumps(body).encode(),
        headers={"X-API-Token": token, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["data"]


def fetch_devices(base_url, token, snapshot):
    return ipfabric_request(
        base_url, token, "/tables/inventory/devices",
        {"columns": ["hostname", "siteName", "vendor", "model", "sn"], "snapshot": snapshot,
         "pagination": {"limit": 1000, "start": 0}},
    )


def fetch_connectivity_matrix(base_url, token, snapshot):
    return ipfabric_request(
        base_url, token, "/tables/interfaces/connectivity-matrix",
        {"columns": ["localHost", "localInt", "remoteHost", "remoteInt", "protocol"], "snapshot": snapshot,
         "pagination": {"limit": 5000, "start": 0}},
    )


def fetch_interface_speeds(base_url, token, snapshot):
    rows = ipfabric_request(
        base_url, token, "/tables/inventory/interfaces",
        {"columns": ["hostname", "intName", "speed"], "snapshot": snapshot,
         "pagination": {"limit": 5000, "start": 0}},
    )
    speeds = {}
    for row in rows:
        speed = row.get("speed")
        if speed:
            speeds[(row["hostname"], row["intName"])] = int(speed)
    return speeds


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
    used to validate the IPFabric->gnmic interface alias before trusting it."""
    results = prom_query(prometheus_url, "interfaces_interface_state_oper_status")
    return {(m["metric"]["device"], m["metric"]["interface"]) for m in results}


def known_vtep_vlan_pairs(prometheus_url):
    """(device, vlan) pairs with a live VLAN-to-VNI mapping -- these are the
    VTEP nodes eligible for a VXLAN MAC-count tooltip metric."""
    results = prom_query(prometheus_url, "interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni")
    return {(m["metric"]["device"], m["metric"]["vlan"]) for m in results}


# --------------------------------------------------------------------------
# Interface aliasing (IPFabric abbreviated name -> gnmic full name)
# --------------------------------------------------------------------------

def alias_interface(ipf_name):
    match = re.match(r"^([A-Za-z]+)(\d.*)$", ipf_name)
    if not match:
        return ipf_name
    prefix, rest = match.groups()
    full = INTERFACE_PREFIX_ALIASES.get(prefix)
    if full is None:
        return ipf_name
    return f"{full}{rest}"


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

def build_layout(devices):
    by_site = {}
    for dev in devices:
        by_site.setdefault(dev["siteName"], []).append(dev["hostname"])

    positions = {}
    for site in SITE_ORDER:
        band_y = SITE_BAND_Y.get(site, 0)
        for idx, host in enumerate(sorted(by_site.get(site, []))):
            col, row = idx % GRID_COLUMNS, idx // GRID_COLUMNS
            positions[host] = [100 + col * GRID_SPACING_X, band_y + row * GRID_SPACING_Y]

    # Any site not in SITE_ORDER (shouldn't happen given the naming convention,
    # but don't silently drop nodes if it does) gets stacked below everything else.
    extra_band_y = max(SITE_BAND_Y.values()) + 300
    for site, hosts in by_site.items():
        if site in SITE_ORDER:
            continue
        for idx, host in enumerate(sorted(hosts)):
            col, row = idx % GRID_COLUMNS, idx // GRID_COLUMNS
            positions[host] = [100 + col * GRID_SPACING_X, extra_band_y + row * GRID_SPACING_Y]
    return positions


def dedupe_links(connectivity_matrix):
    """connectivity-matrix reports each physical link twice (once from each
    side), plus management-plane (Management0) neighbor entries, plus one row
    per 802.1Q subinterface on trunked ports (e.g. Et13.100/Et13.200, used for
    the gold VRF stitching on Core -- see README). Subinterfaces ride the same
    physical port as their parent interface, so they'd otherwise show up as
    bogus duplicate parallel links with permanently-unresolvable queries
    (gnmic only subscribes to physical interface counters). Keep only
    physical Ethernet-to-Ethernet links, one entry per unordered
    (host,int)-(host,int) pair."""
    seen = set()
    links = []
    for row in connectivity_matrix:
        local_int, remote_int = row["localInt"], row["remoteInt"]
        if "." in local_int or "." in remote_int:
            continue
        if not (local_int.startswith("Et") and remote_int.startswith("Et")):
            continue
        side_a = (row["localHost"], local_int)
        side_z = (row["remoteHost"], remote_int)
        key = tuple(sorted([side_a, side_z]))
        if key in seen:
            continue
        seen.add(key)
        links.append({"a_host": key[0][0], "a_int": key[0][1], "z_host": key[1][0], "z_int": key[1][1]})
    return links


# --------------------------------------------------------------------------
# Weathermap assembly
# --------------------------------------------------------------------------

def build_weathermap(devices, links, interface_speeds, positions, prometheus_url, mismatches):
    hostnames = [d["hostname"] for d in devices]
    host_regex = "|".join(promql_escape(h) for h in hostnames)

    known_pairs = known_interface_pairs(prometheus_url)
    vtep_vlan_pairs = known_vtep_vlan_pairs(prometheus_url)
    vtep_hosts = sorted({dev for dev, _ in vtep_vlan_pairs})

    def resolve_and_check(host, ipf_int, side_label):
        gnmic_int = alias_interface(ipf_int)
        if (host, gnmic_int) not in known_pairs:
            mismatches.append(
                f"{host} {ipf_int} -> {gnmic_int} ({side_label}): no matching series in "
                f"interfaces_interface_state_oper_status -- link will reference a query that "
                f"resolves to no data until the gnmic/IPFabric interface names are aligned "
                f"(see #47/#48 interface aliasing fallback)"
            )
        return gnmic_int

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
            "compactVerticalLinks": False,
            "padding": {"horizontal": 12, "vertical": 6},
            "colors": dict(NODE_COLORS),
            "nodeIcon": None,
            "statusQuery": f"BGP {host}",
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
        a_gnmic_int = resolve_and_check(link["a_host"], link["a_int"], "side A")
        z_gnmic_int = resolve_and_check(link["z_host"], link["z_int"], "side Z")
        interface_regex_parts.add(promql_escape(a_gnmic_int))
        interface_regex_parts.add(promql_escape(z_gnmic_int))

        a_bw = interface_speeds.get((link["a_host"], link["a_int"]), DEFAULT_LINK_BANDWIDTH_BPS)
        z_bw = interface_speeds.get((link["z_host"], link["z_int"]), DEFAULT_LINK_BANDWIDTH_BPS)
        if (link["a_host"], link["a_int"]) not in interface_speeds:
            mismatches.append(f"{link['a_host']} {link['a_int']}: no IPFabric speed, defaulting bandwidth to {DEFAULT_LINK_BANDWIDTH_BPS}")
        if (link["z_host"], link["z_int"]) not in interface_speeds:
            mismatches.append(f"{link['z_host']} {link['z_int']}: no IPFabric speed, defaulting bandwidth to {DEFAULT_LINK_BANDWIDTH_BPS}")

        link_defs.append({
            "id": f"{link['a_host']}-{a_gnmic_int}--{link['z_host']}-{z_gnmic_int}",
            "nodes": [{"id": link["a_host"]}, {"id": link["z_host"]}],
            "sides": {
                "A": {
                    "bandwidth": a_bw,
                    "query": f"{link['a_host']} {a_gnmic_int} tx",
                    "labelOffset": 55, "anchor": ANCHOR["Right"], "dashboardLink": "",
                },
                "Z": {
                    "bandwidth": z_bw,
                    "query": f"{link['z_host']} {z_gnmic_int} rx",
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
    targets = [
        {
            "refId": "A",
            "expr": f'min by (device) (network_instances_network_instance_protocols_protocol_bgp_neighbors_neighbor_state_session_state{{network_instance_name="default", device=~"{host_regex}"}})',
            "legendFormat": "BGP {{device}}",
        },
        {
            "refId": "B",
            "expr": f'rate(interfaces_interface_state_counters_out_octets{{device=~"{host_regex}", interface=~"{interface_regex}"}}[5m]) * 8',
            "legendFormat": "{{device}} {{interface}} tx",
        },
        {
            "refId": "C",
            "expr": f'rate(interfaces_interface_state_counters_in_octets{{device=~"{host_regex}", interface=~"{interface_regex}"}}[5m]) * 8',
            "legendFormat": "{{device}} {{interface}} rx",
        },
    ]
    if vtep_hosts:
        vtep_regex = "|".join(promql_escape(h) for h in vtep_hosts)
        # Verbatim join from #44 "VXLAN (MAC count per VNI)", scoped to VTEP nodes.
        targets.append({
            "refId": "D",
            "expr": (
                f'count by (device, vlan) (network_instances_network_instance_fdb_mac_table_entries_entry_vlan{{device=~"{vtep_regex}"}})\n'
                f'* on(device, vlan) group_left(vlan_to_vni_state_vni)\n'
                f'interfaces_interface_arista_vxlan_vlan_to_vnis_vlan_to_vni_state_vni{{device=~"{vtep_regex}"}}'
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
# Grafana provisioning
# --------------------------------------------------------------------------

def build_dashboard(weathermap, targets, dashboard_uid, datasource_uid, plugin_id):
    return {
        "dashboard": {
            "uid": dashboard_uid,
            "title": "EVPN/VXLAN Fabric Weathermap",
            "tags": ["evpn", "vxlan", "weathermap", "auto-generated"],
            "timezone": "browser",
            "schemaVersion": 39,
            "version": 0,
            "panels": [
                {
                    "id": 1,
                    "type": plugin_id,
                    "title": "Fabric Weathermap",
                    "gridPos": {"h": 24, "w": 24, "x": 0, "y": 0},
                    "datasource": {"type": "prometheus", "uid": datasource_uid},
                    "targets": [dict(t, datasource={"type": "prometheus", "uid": datasource_uid}) for t in targets],
                    "options": {"weathermap": weathermap},
                }
            ],
        },
        "overwrite": True,
    }


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
    parser.add_argument("--output", default="configs/grafana/weathermap-dashboard.json",
                         help="where to write the generated dashboard-as-code JSON")
    parser.add_argument("--provision", action="store_true",
                         help="also POST the dashboard to the Grafana API (requires GRAFANA_* env vars)")
    args = parser.parse_args()

    ipfabric_url = env("IPFABRIC_URL", required=True)
    ipfabric_token = env("IPFABRIC_TOKEN", required=True)
    snapshot = env("IPFABRIC_SNAPSHOT", "$last")
    prometheus_url = env("PROMETHEUS_URL", "http://172.16.0.71:9090")

    print(f"Fetching devices from IPFabric ({ipfabric_url}, snapshot={snapshot})...")
    devices = fetch_devices(ipfabric_url, ipfabric_token, snapshot)
    print(f"  {len(devices)} devices")

    print("Fetching connectivity-matrix...")
    matrix = fetch_connectivity_matrix(ipfabric_url, ipfabric_token, snapshot)
    links = dedupe_links(matrix)
    print(f"  {len(links)} fabric links after Management-plane filter + dedup ({len(matrix)} raw rows)")

    print("Fetching interface speeds...")
    interface_speeds = fetch_interface_speeds(ipfabric_url, ipfabric_token, snapshot)

    positions = build_layout(devices)

    mismatches = []
    print(f"Cross-checking interface names against live exporter ({prometheus_url})...")
    weathermap, targets = build_weathermap(devices, links, interface_speeds, positions, prometheus_url, mismatches)

    if mismatches:
        print(f"\n{len(mismatches)} interface-name / bandwidth mismatch(es) found (link kept, not dropped):", file=sys.stderr)
        for m in mismatches:
            print(f"  - {m}", file=sys.stderr)
        print(file=sys.stderr)

    dashboard_uid = env("GRAFANA_DASHBOARD_UID", "evpn-vxlan-fabric-weathermap")
    datasource_uid = env("GRAFANA_DATASOURCE_UID", "PROMETHEUS_DATASOURCE_UID_PLACEHOLDER")
    plugin_id = env("GRAFANA_WEATHERMAP_PLUGIN_ID", "allamiro-weathermap-panel")
    dashboard_payload = build_dashboard(weathermap, targets, dashboard_uid, datasource_uid, plugin_id)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(dashboard_payload, f, indent=2)
        f.write("\n")
    print(f"Wrote {args.output} ({len(weathermap['nodes'])} nodes, {len(weathermap['links'])} links)")

    if args.provision:
        grafana_url = env("GRAFANA_URL", required=True)
        grafana_token = env("GRAFANA_TOKEN", required=True)
        if datasource_uid == "PROMETHEUS_DATASOURCE_UID_PLACEHOLDER":
            sys.exit("Refusing to provision: set GRAFANA_DATASOURCE_UID to the real Prometheus datasource UID first")
        print(f"Provisioning dashboard '{dashboard_uid}' to {grafana_url}...")
        result = provision_to_grafana(grafana_url, grafana_token, dashboard_payload)
        print(f"  {result.get('status')}: {result.get('url')}")


if __name__ == "__main__":
    main()
