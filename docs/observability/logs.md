# Logs

Syslog from every `cEOS` node and logs from the AAA servers go through Grafana Alloy into
Loki, and are queried from Grafana next to the Prometheus metrics.

```
28 cEOS ── UDP 514  (RFC5424) ──┐
tac_plus-ng ── UDP 1514 (RFC3164) ──┼─> alloy (.73) ──> loki (.72) <── grafana (.74)
FreeRADIUS ── UDP 1515 (busybox relay) ┘
```

| Source       | Transport                                                 | Format                      |
| ------------ | --------------------------------------------------------- | --------------------------- |
| cEOS         | `logging host 172.16.0.73`, `logging format rfc5424`      | RFC5424                     |
| tac_plus-ng  | `log alloy { destination = 172.16.0.73:1514 }`            | RFC3164, fields split by `\|` |
| FreeRADIUS   | `linelog` to syslog(3), busybox `syslogd -R` to `:1515`   | RFC3164 relay, logfmt body  |

FreeRADIUS 3.2 `linelog` cannot send syslog over the network, and containerlab binds
need an existing host path, so a shared log file is not an option: busybox `syslogd`
in the `radius` container relays it. The relay sends no hostname or tag, Alloy sets
`host`/`app` on that listener and strips the empty `: ` prefix.

Config: `configs/alloy/config.alloy`. Loki runs with the image default config
(filesystem storage, data lost on `containerlab destroy`).

## Labels

| Label      | Values                                                     | Source                            |
| ---------- | ---------------------------------------------------------- | --------------------------------- |
| `source`   | `network` (cEOS), `aaa` (tac_plus-ng, FreeRADIUS)          | listener                          |
| `host`     | node hostname, `tacacs`, `radius`                          | syslog hostname / static          |
| `app`      | EOS agent (`Bgp`, `Stp`, `ConfigAgent`...), `tacplus`, `freeradius` | syslog APP-NAME, trailing `:` stripped |
| `severity` | syslog severity                                            | syslog                            |
| `site`     | `dc`, `campus`, `core`                                     | hostname, same regex as [Prometheus](prometheus.md) |

## Message formats

tac_plus-ng (`|`-separated):

```
AUTHC-PASS|<nas>|<user>|<port>|<client>|shell login succeeded
AUTHZ-PASS|<nas>|<user>|<port>|<client>|<profile>|permit|shell|<cmd>
ACCT-STOP|<nas>|<user>|<port>|<client>|stop|shell|<cmd>
```

`<port>` is `ssh`, or `gRPC` for gNMI sessions (gnmic).

FreeRADIUS (logfmt, `configs/freeradius/lab_log`):

```
event=login_ok user=campus-user1 nas=172.16.0.61 port=Ethernet3 mac=AA-C1-AB-9E-99-DB eap=PEAP
event=acct_Start user=aa:c1:ab:60:02:01 nas=172.16.0.62 port=Ethernet3 mac=AA-C1-AB-60-02-01 session=...
```

`event`: `login_ok`, `login_fail`, `acct_Start`, `acct_Stop`, `acct_Interim-Update`.

## LogQL examples

| Need                                    | Query                                                                                       |
| --------------------------------------- | ------------------------------------------------------------------------------------------- |
| All logs from the Campus fabric         | `{source="network", site="campus"}`                                                         |
| Config changes                          | `{source="network"} \|= "SYS-5-CONFIG_I"`                                                   |
| BGP events                              | `{source="network", app="Bgp"}`                                                             |
| Log volume per node                     | `sum by (host) (count_over_time({source="network"}[1h]))`                                   |
| Commands typed, per user                | `{app="tacplus"} \|= "ACCT-STOP" \| pattern "<type>\|<nas>\|<user>\|<port>\|<client>\|<_>\|<service>\|<cmd>"` |
| Denied commands                         | `{app="tacplus"} \|= "AUTHZ-FAIL"`                                                          |
| 802.1X / MAB results                    | `{app="freeradius"} \| logfmt \| event=~"login_.*"`                                         |
| RADIUS events per type                  | `sum by (event) (count_over_time({app="freeradius"} \| logfmt [1h]))`                      |

## Grafana

`http://172.16.0.74:3000` (through the Tailscale subnet route), `admin` / `evpnlab-grafana`.
Everything is provisioned from files at start, nothing to import:

| Item | File | Content |
| ---- | ---- | ------- |
| Datasources | `configs/grafana/provisioning/datasources/lab.yml` | `Prometheus` (UID `prometheus`), `Loki` (UID `loki`) |
| Dashboard provider | `configs/grafana/provisioning/dashboards/lab.yml` | loads `configs/grafana/dashboards/*.json` |
| EVPN/VXLAN Fabric Weathermap | `configs/grafana/dashboards/fabric.json` | weathermap (link load, node status), BGP sessions, ports, throughput per site. Generated, see [Weathermap](weathermap.md) |
| EVPN Lab: Logs | `configs/grafana/dashboards/logs.json` | syslog volume per site and per node, errors/warnings, all logs (`site`/`host` filters), TACACS+ events, failures and typed commands, 802.1X/MAB results |
| Weathermap plugin | `evpn-lab.clab.yml` (`GF_PLUGINS_PREINSTALL_SYNC`) | `tamirsuliman-weathermap-panel`, pinned, downloaded at start (needs internet) |

Dashboards can be edited and saved in the UI, but Grafana has no persistent volume:
export the JSON into `configs/grafana/dashboards/` and commit it to keep a change.
Traffic for the throughput panels and the weathermap: `./scripts/generate_traffic.sh 120`.
