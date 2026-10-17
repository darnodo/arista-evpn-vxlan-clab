# NetMapper

[NetMapper](https://github.com/darnodo/NetMapper) crawls the lab read-only over SNMPv3 and
SSH, starting from two seeds and following LLDP, and serves the resulting graph (devices,
interfaces, links) over a REST API. It is the topology source for the weathermap (#11), the
same way it would be on a network that is not a containerlab lab.

## Nodes

| Node                  | IP            | Image                              | Role                                                  |
| --------------------- | ------------- | ---------------------------------- | ----------------------------------------------------- |
| `netmapper-db`        | `172.16.0.78` | `postgres:17`                      | graph, observations, tokens                           |
| `netmapper-s3`        | `172.16.0.79` | `dxflrs/garage:v2.1.0`             | raw command output (S3 `:3900`, admin `:3903`)        |
| `netmapper-engine`    | `172.16.0.80` | `ghcr.io/darnodo/netmapper:v0.6.1` | closes snapshots, judges coverage, projects the graph |
| `netmapper-collector` | `172.16.0.81` | same                               | the only node with device credentials                 |
| `netmapper-api`       | `172.16.0.82` | same                               | read API, `http://172.16.0.82:8080/v1/...`, bearer token |

Postgres and Garage keep no volume: `containerlab destroy` or a redeploy starts from an
empty graph, rerun the setup script.

### Restart loop until the setup script runs

After every `containerlab deploy`, `netmapper-engine`, `netmapper-collector` and
`netmapper-api` show `Restarting` in `docker ps`: their Postgres login (`nm_engine`, ...)
does not exist yet, the process exits 1 and Docker restarts it (`restart: always`, set by
containerlab). Expected and harmless: nothing is crawled or served meanwhile, only error
lines in `docker logs`. The setup script creates the logins and restarts the three
nodes, which then stay `Up`.

## Setup and crawl

```bash
sudo containerlab deploy -t evpn-lab.clab.yml
./scripts/netmapper_setup.sh   # rerun it to crawl again
```

| Step | What | Idempotent |
| ---- | ---- | ---------- |
| 1 | Garage layout, bucket `netmapper`, collector key (read/write), API key (read only) | yes, existing objects kept |
| 2 | `netmapper migrate`, one Postgres login per process (`nm_engine`, `nm_collector`, `nm_api`, `nm_operator`) | yes |
| 3 | API token (`read` scope) written to `clab-arista-evpn-fabric/netmapper/token` | created once per deploy |
| 4 | `netmapper run` with [`configs/netmapper/netmapper.yaml`](../../configs/netmapper/netmapper.yaml), waits for the graph | new crawl on every run |

Operator commands run as a one-shot container in `netmapper-db`'s network namespace (no
mgmt IP taken; the engine crash-loops until its login exists, so no `docker exec` there):

```bash
docker run --rm --network container:clab-arista-evpn-fabric-netmapper-db \
    -e NETMAPPER_DSN='postgres://nm_operator:evpnlab-nm-operator@172.16.0.78:5432/netmapper?sslmode=disable' \
    ghcr.io/darnodo/netmapper:v0.6.1 token list
```

## Crawl document

| Item | Value |
| ---- | ----- |
| Perimeter | `172.16.0.0/24` minus `172.16.0.254` (gateway) |
| Seeds | `dc-spine1` (`172.16.0.1`), `campus-spine1` (`172.16.0.20`) |
| SNMPv3 | `snmp-ro`, SHA-256 / AES-128, see [SNMP](snmp.md) |
| SSH | `netmapper`, see below |

## Crawl account

`netmapper` exists on every cEOS node, in TACACS+ and locally (fallback when no TACACS+
server answers). Privilege 15 is needed for `show running-config sanitized`, `show users
accounts` and `show aaa methods all`; it cannot configure:

| Where | Restriction |
| ----- | ----------- |
| TACACS+ (`tac_plus-ng.cfg`, profile `collector`) | priv-lvl 15, `show` commands only, everything else denied |
| Local (`configs/<node>.cfg`) | `role network-operator`: no `configure` |

## Reading the API

```bash
TOKEN=$(cat clab-arista-evpn-fabric/netmapper/token)
curl -s -H "Authorization: Bearer $TOKEN" http://172.16.0.82:8080/v1/snapshots | jq
curl -s -H "Authorization: Bearer $TOKEN" http://172.16.0.82:8080/v1/devices | jq '.devices[].hostname'
curl -s -H "Authorization: Bearer $TOKEN" http://172.16.0.82:8080/v1/devices/dc-leaf1.evpnlab.local | jq '.edges'
```

Full contract: [NetMapper REST API](https://github.com/darnodo/NetMapper/blob/main/specs/005-read-api/contracts/rest.md).

| What the lab returns | Note |
| -------------------- | ---- |
| Hostnames as FQDN (`dc-leaf1.evpnlab.local`) | gnmic's `device` label is the short name |
| `l1_link` edges between `Management0` ports | LLDP across the docker mgmt bridge, not a cable: ignore `Management*` |
| No edge to Linux hosts | no LLDP on `network-multitool` |

## Lab vs production

| Item | Lab | Production |
| ---- | --- | ---------- |
| Device secrets | `env:` references, values in `evpn-lab.clab.yml` | `vault:<kv path>` references, OpenBao |
| Postgres / S3 credentials | shared `evpnlab-` values | one secret per process |
| Deployment | containerlab nodes | Komodo, API reachable over Tailnet only |
| Crawl trigger | `scripts/netmapper_setup.sh` | scheduled `netmapper run` |
