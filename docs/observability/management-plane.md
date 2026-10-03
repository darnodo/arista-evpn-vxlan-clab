# Management plane

Management services running as containerlab nodes on the mgmt subnet, and the matching
config block on every Arista `cEOS` node (28 nodes). Main consumers: the lab itself
(playground for the services) and NetMapper (management-plane inventory, darnodo/NetMapper#25).

> **Shared lab values.** Every password, key and community below is committed on purpose,
> like [SNMPv3](snmp.md). All values start with `evpnlab-` so a test can grep a fixed list.
> Never reuse them outside this lab.

## Services

| Node      | IP            | Image                                        | Role                                                    |
| --------- | ------------- | -------------------------------------------- | ------------------------------------------------------- |
| `loki`    | `172.16.0.72` | `grafana/loki:3.7.8`                         | log store, see [Logs](logs.md)                          |
| `alloy`   | `172.16.0.73` | `grafana/alloy:v1.20.1`                      | syslog receiver, forwards to Loki                       |
| `grafana` | `172.16.0.74` | `grafana/grafana-oss:13.0.2`                 | UI on `:3000`, datasources Prometheus + Loki            |
| `tacacs`  | `172.16.0.75` | `evpnlab/tac_plus-ng` (local build)          | TACACS+ for device administration, all nodes            |
| `radius`  | `172.16.0.76` | `freeradius/freeradius-server:3.2.10-alpine` | RADIUS for 802.1X/MAB, `campus-access1-2` only          |
| `dns`     | `172.16.0.77` | `coredns/coredns:1.14.7`                     | `evpnlab.local` zone, A + PTR for every node            |
| (none)    | `172.16.0.99` | -                                            | dead IP, second server for TACACS+, RADIUS, DNS, syslog |

- Local images: `./scripts/build_images.sh` before `containerlab deploy` (containerlab
  cannot build images). tac_plus-ng has no official image, the Dockerfile pins an
  upstream commit; FreeRADIUS 3.2 has no TACACS+ support (only the unreleased v4).
- Each service has an active server listed first and the dead IP second: config shows
  two servers, failover can be tested, normal logins are not slowed down.
- NTP: config only (`172.16.0.254`, `172.16.0.99`), no NTP server in the lab, no
  internet access from the mgmt network.

| Service    | Config files                                                  |
| ---------- | ------------------------------------------------------------- |
| tac_plus-ng | `configs/tacacs/tac_plus-ng.cfg`, `images/tac_plus-ng/Dockerfile` |
| FreeRADIUS | `configs/freeradius/{clients.conf,authorize,default,lab_log}` |
| Alloy      | `configs/alloy/config.alloy`                                  |
| Grafana    | `configs/grafana/provisioning/`                               |
| CoreDNS    | `configs/coredns/{Corefile,lab.hosts}`                        |

`configs/coredns/lab.hosts` lists every node of `evpn-lab.clab.yml` with its
`mgmt-ipv4`; update it with the topology.

## Lab secrets

| Item                     | Where                                     | Value                                    |
| ------------------------ | ----------------------------------------- | ---------------------------------------- |
| SNMPv2c ro community     | all nodes, ACL `SNMP-RO` (`172.16.0.0/24`) | `evpnlab-ro`                             |
| SNMPv2c rw community     | all nodes, ACL `SNMP-RW` (`172.16.0.254`) | `evpnlab-rw`                             |
| SNMPv3 `snmp-ro` (authPriv) | all nodes                              | `evpnlab-auth` / `evpnlab-priv`, see [SNMP](snmp.md) |
| SNMPv3 `snmp-auth` (authNoPriv) | all nodes, group `lab-auth`        | auth SHA-256 `evpnlab-authonly`          |
| TACACS+ key              | all nodes, `tac_plus-ng.cfg`              | `evpnlab-tacacs`                         |
| RADIUS key               | `campus-access1-2`, `clients.conf`        | `evpnlab-radius`                         |
| User `admin`             | TACACS+ and local                         | `admin` (pre-existing, not prefixed)     |
| User `netops` (read-only) | TACACS+ and local                        | `evpnlab-netops`                         |
| User `automation`        | TACACS+ and local, local SSH key          | `evpnlab-automation`                     |
| 802.1X user `campus-user1` | FreeRADIUS, `campus-host1` supplicant   | `evpnlab-user1`                          |
| MAB `campus-host2`       | FreeRADIUS                                | MAC `aa:c1:ab:60:02:01` (user = password) |
| Grafana `admin`          | `evpn-lab.clab.yml`                       | `evpnlab-grafana`                        |

The `automation` SSH key is a lab public key (comment `automation@evpn-lab`), its
private key is not in the repo. To log in with a key, replace the `ssh-key` line with
your own public key.

## EOS configuration

One block on every node, after the SNMP block in `configs/<node>.cfg`:

| Item            | Config                                                                                       |
| --------------- | -------------------------------------------------------------------------------------------- |
| SNMPv2c         | `snmp-server community evpnlab-ro ro SNMP-RO`, `... evpnlab-rw rw SNMP-RW`, standard ACLs     |
| SNMPv3          | second user `snmp-auth`, group `lab-auth v3 auth`                                            |
| Local users     | `netops` (`network-operator`, priv 1), `automation` (`network-admin`, priv 15, SSH key)      |
| TACACS+         | `tacacs-server host 172.16.0.75`, `.99`, group `LAB-TACACS`, timeout 2 s, source `Management0` |
| AAA login       | `default`: `group LAB-TACACS local`; `console`: `local`                                      |
| AAA enable      | `default`: `group LAB-TACACS local`                                                          |
| AAA authorization | `exec` and `commands all`: `group LAB-TACACS local`                                        |
| AAA accounting  | `exec` and `commands all`: `start-stop group LAB-TACACS`                                     |
| eAPI            | `management api http-commands` / `no shutdown` (HTTPS `443`)                                 |
| NETCONF         | `management api netconf` / `transport ssh default` (port `830`)                              |
| Telnet          | `management telnet` / `shutdown`                                                             |
| NTP             | `ntp server 172.16.0.254 prefer`, `ntp server 172.16.0.99`                                   |
| Syslog          | `logging format rfc5424`, `logging host 172.16.0.73` (UDP 514), `logging host 172.16.0.99 1514`, trap `informational` |
| DNS             | `ip name-server vrf default 172.16.0.77`, `.99`, `dns domain evpnlab.local`                  |

Everything stays in VRF `default` (`Management0` is not in a management VRF).

`campus-access1` and `campus-access2` only:

| Item       | Config                                                                                      |
| ---------- | ------------------------------------------------------------------------------------------- |
| RADIUS     | `radius-server host 172.16.0.76`, `.99`, group `LAB-RADIUS`, timeout 2 s, source `Management0` |
| AAA dot1x  | `aaa authentication dot1x default group LAB-RADIUS`, `aaa accounting dot1x default start-stop group LAB-RADIUS` |
| 802.1X     | `dot1x system-auth-control`; `Ethernet3`: `dot1x pae authenticator`, `dot1x port-control auto` |
| MAB        | `campus-access2` `Ethernet3`: `dot1x mac based authentication`                              |

## TACACS+ behaviour

| Case                                   | Result                                                               |
| -------------------------------------- | -------------------------------------------------------------------- |
| `tacacs` up                            | SSH login < 1 s, every command authorized and logged                 |
| `netops`                               | `show` commands only, `configure` and `enable` denied                |
| User only in local accounts, `tacacs` up | rejected: EOS falls back to `local` only when no server answers, not on reject |
| `tacacs` down                          | local fallback works, ~13 s per login (2 s timeout on both servers)  |
| gNMI (gnmic, user `admin`)             | goes through TACACS+ (port `gRPC` in the logs): authc, exec authz and accounting |

Every user that logs in must therefore exist in `configs/tacacs/tac_plus-ng.cfg`.
`docker exec ... Cli` does not go through AAA.

## 802.1X / MAB

| Host           | Switch port            | Method                         | VLAN |
| -------------- | ---------------------- | ------------------------------ | ---- |
| `campus-host1` | `campus-access1` `Et3` | 802.1X PEAP-MSCHAPv2 (`wpa_supplicant`) | 60   |
| `campus-host2` | `campus-access2` `Et3` | MAB, fixed MAC `aa:c1:ab:60:02:01` | 70   |

- The port blocks all traffic until the host is authorized.
- `dot1x pae authenticator` is required: without it EOS accepts the rest of the config
  but ignores EAPOL, and the port forwards without authentication.
- Not supported on `Port-Channel` interfaces: DC hosts (LACP) are not authenticated.
- RADIUS down: both servers time out, the host stays unauthorized (fail-closed).
- MAB: EOS sends the MAC as `User-Name` and password, lowercase with colons.
- `campus-host1` uses its own image (`evpnlab/network-multitool-8021x`, adds
  `wpa_supplicant`); FreeRADIUS uses its default test certificate for PEAP.
- Dynamic VLAN assignment: #13.

## Secrets in command output

Checked on `campus-access1` (cEOS 4.36.0F) against every value of the table above.

| Command                                | Rows | Secrets shown                                               |
| -------------------------------------- | ---- | ----------------------------------------------------------- |
| `show running-config sanitized`        | yes  | none: communities, keys, hashes, SNMPv3 keys replaced by `<removed>` |
| `show snmp community`                  | yes  | **communities in clear** (`evpnlab-ro`, `evpnlab-rw`)        |
| `show snmp user`, `show snmp group`, `show snmp host` | yes | none                                         |
| `show radius`, `show tacacs`           | yes  | none                                                        |
| `show users accounts`                  | yes  | none (role, privilege, SSH public key)                      |
| `show management api gnmi` / `http-commands` / `netconf`, `show management ssh`, `show management telnet` | yes | none |
| `show aaa methods all`                 | yes  | none                                                        |
| `show ntp associations`                | yes  | none                                                        |
| `show logging`                         | yes  | none                                                        |
| `show ip name-server`                  | yes  | none                                                        |
| `show dot1x hosts`                     | yes  | none (802.1X user name, MAB MAC)                            |

- `show running-config` (not sanitized) shows TACACS+/RADIUS keys as type 7
  (reversible), user hashes (`sha512`) and localized SNMPv3 keys.
- EOS 4.36 has no `show user-account`: use `show users accounts`.

Verification commands: [Validation: management plane](../operations/validation.md#management-plane).
