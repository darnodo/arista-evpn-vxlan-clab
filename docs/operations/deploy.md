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

sudo containerlab deploy -t evpn-lab.clab.yml
sudo containerlab inspect -t evpn-lab.clab.yml
```

## Access Devices

```bash
# SSH (password: admin) — works for every cEOS node
ssh admin@clab-arista-evpn-fabric-leaf1
ssh admin@clab-arista-evpn-fabric-core1
ssh admin@clab-arista-evpn-fabric-campus-leaf1

# Or via docker exec
docker exec -it clab-arista-evpn-fabric-dc-border-leaf1 Cli
```

## 🗑️ Cleanup

```bash
sudo containerlab destroy -t evpn-lab.clab.yml --cleanup
```
