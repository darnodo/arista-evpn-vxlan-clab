# 🚀 Quick Start

## Prerequisites

- ContainerLab
- Docker
- Arista cEOS image, imported locally and tagged `ceos:4.36.0F`

## Import the cEOS image

cEOS is not redistributable, so it isn't pulled from any registry — download the
`cEOS64-lab-4.36.0F.tar.xz` image from Arista (support portal) and import it manually:

```bash
docker import cEOS64-lab-4.36.0F.tar.xz ceos:4.36.0F
```

## Deploy the Lab

```bash
git clone https://github.com/darnodo/arista-evpn-vxlan-clab.git
cd arista-evpn-vxlan-clab

# local images (tac_plus-ng, 802.1X host), containerlab cannot build them; skips existing ones
./scripts/build_images.sh

sudo containerlab deploy -t evpn-lab.clab.yml
sudo containerlab inspect -t evpn-lab.clab.yml
```

## Access Devices

```bash
# SSH (password: admin), authenticated by TACACS+ on every cEOS node
# other users and fallback behaviour: docs/observability/management-plane.md
ssh admin@clab-arista-evpn-fabric-leaf1
ssh admin@clab-arista-evpn-fabric-core1
ssh admin@clab-arista-evpn-fabric-campus-leaf1

# Or via docker exec
docker exec -it clab-arista-evpn-fabric-dc-border-leaf1 Cli
```

## Web UIs

| Service    | URL                         | Login                       |
| ---------- | --------------------------- | --------------------------- |
| Grafana    | `http://172.16.0.74:3000`   | `admin` / `evpnlab-grafana` |
| Prometheus | `http://172.16.0.71:9090`   | none                        |

Reachable from the lab host, or remotely through the Tailscale subnet route to
`172.16.0.0/24`.

## 🗑️ Cleanup

```bash
sudo containerlab destroy -t evpn-lab.clab.yml --cleanup
```
