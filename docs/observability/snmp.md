# SNMP

SNMPv3 read-only agent enabled on every Arista `cEOS` node (DC, Core, Campus — 28 nodes),
reachable on the management network (`Management0`, VRF `default`, UDP `161`).
Main consumer: Zabbix LLDP neighbour discovery (`LLDP-MIB`).

> **Shared lab credentials.** The values below are **not secret**: they are committed in
> `configs/*.cfg` on purpose so anyone deploying the lab can poll it. Never reuse them
> outside this lab.

## Credentials

| Parameter        | Value          | `envrc.sample` var |
| ---------------- | -------------- | ------------------ |
| Version          | `v3`           | —                  |
| Security level   | `authPriv`     | —                  |
| User             | `snmp-ro`      | `SNMP_USER`        |
| Auth protocol    | `SHA-256`      | `SNMP_AUTH_PROTO`  |
| Auth passphrase  | `evpnlab-auth` | `SNMP_AUTH_PASS`   |
| Priv protocol    | `AES-128`      | `SNMP_PRIV_PROTO`  |
| Priv passphrase  | `evpnlab-priv` | `SNMP_PRIV_PASS`   |
| Context          | none           | —                  |

## EOS configuration

Identical block on every node, right after `management api gnmi`:

```
snmp-server view all iso included
snmp-server group lab-ro v3 priv read all
snmp-server user snmp-ro lab-ro v3 auth sha256 evpnlab-auth priv aes evpnlab-priv
```

| Object | Role                                                        |
| ------ | ----------------------------------------------------------- |
| `all`  | view covering the whole `iso` tree (incl. `LLDP-MIB`)       |
| `lab-ro` | v3 group, `priv` required, read-only on view `all`        |
| `snmp-ro` | v3 user; EOS stores it localized (`localized <engineID>` + hashes) in `running-config` |

- EngineID is auto-generated per node from its chassis ID — unique across the 28 nodes, not
  pinned in the configs
- No write access, no traps, no v1/v2c community

## Validation

Target IPs: `mgmt-ipv4` of each node in `evpn-lab.clab.yml`. No `snmpwalk` on the host?
Use a throwaway container on the lab management network:

```bash
docker run --rm -it --network evpn-mgmt alpine:3 sh -c 'apk add -q net-snmp-tools && sh'
```

```bash
A="-v3 -l authPriv -u snmp-ro -a SHA-256 -A evpnlab-auth -x AES -X evpnlab-priv"

# System
snmpget $A 172.16.0.25 sysName.0

# LLDP-MIB lldpRemSysName (1.0.8802.1.1.2.1.4.1.1.9) — one entry per LLDP neighbour
snmpwalk $A 172.16.0.25 1.0.8802.1.1.2.1.4.1.1.9

# snmpEngineID (must differ between nodes)
snmpget $A 172.16.0.25 1.3.6.1.6.3.10.2.1.1.0
```

Expected `lldpRemSysName` count per role:

| Role                          | Neighbours |
| ----------------------------- | ---------- |
| `dc-spine*`                   | 10         |
| `campus-spine*`               | 6          |
| `core*`, `*-border-leaf*`     | 5          |
| `dc-leaf*`, `campus-leaf*`    | 4          |
| `dc-access*`, `campus-access*` | 2         |

On the switch:

```bash
docker exec -it clab-arista-evpn-fabric-dc-leaf1 Cli -p 15 -c "show snmp user"
docker exec -it clab-arista-evpn-fabric-dc-leaf1 Cli -p 15 -c "show snmp"   # packet counters
```

## Zabbix host settings

| Field                          | Value                        |
| ------------------------------ | ---------------------------- |
| Interface                      | SNMP, `mgmt-ipv4`, port `161` |
| SNMP version                   | `SNMPv3`                     |
| Security name                  | `snmp-ro`                    |
| Security level                 | `authPriv`                   |
| Authentication protocol / pass | `SHA256` / `evpnlab-auth`    |
| Privacy protocol / pass        | `AES128` / `evpnlab-priv`    |
| Context name                   | empty                        |
