# Arista EVPN-VXLAN ContainerLab — DC + Core + Campus

An extended Arista BGP EVPN-VXLAN multi-fabric lab using ContainerLab and cEOS. The topology interconnects a **Data Center fabric** and a **Campus fabric** through a dedicated **Core L3 transit zone**, with a VRF (`gold`) stretched end-to-end across both fabrics.

## 🎯 Overview

| Zone   | Devices                                                                                |
| ------ | -------------------------------------------------------------------------------------- |
| DC     | 2 spines, 8 leafs (4 MLAG VTEPs), 2 border leafs (MLAG), 4 access switches, 4 hosts    |
| Core   | 2 core routers (iBGP AS 65500, OSPF between core1/core2 only, eBGP to DC & Campus BLs) |
| Campus | 2 spines, 4 leafs (2 MLAG VTEPs), 2 border leafs (MLAG), 2 access switches, 2 hosts    |

## 📐 Topology

![Topology](assets/evpn-lab.clab.svg)

## 🚀 Quick Start

### Prerequisites

- ContainerLab
- Docker
- Arista cEOS image, imported locally and tagged `ceos:4.36.0F`

### Deploy the Lab

```bash
git clone https://github.com/darnodo/arista-evpn-vxlan-clab.git
cd arista-evpn-vxlan-clab

sudo containerlab deploy -t evpn-lab.clab.yml
sudo containerlab inspect -t evpn-lab.clab.yml
```

### Access Devices

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

## Documentation

Full documentation lives under [`docs/`](docs/README.md):

- [Architecture](docs/architecture/overview.md)
- [Addressing](docs/architecture/addressing.md)
- [Control Plane](docs/architecture/control-plane.md)
- [VXLAN](docs/architecture/vxlan.md)
- [Deploy](docs/operations/deploy.md)
- [Validation](docs/operations/validation.md)
- [Troubleshooting](docs/operations/troubleshooting.md)
- [Observability](docs/observability/)

## 📚 References

- [Arista EOS Documentation](https://www.arista.com/en/support/product-documentation)
- [ContainerLab Documentation](https://containerlab.dev/)
- [RFC 7432 — BGP MPLS-Based Ethernet VPN](https://tools.ietf.org/html/rfc7432)
- [RFC 8365 — A Network Virtualization Overlay Solution Using EVPN](https://tools.ietf.org/html/rfc8365)
- [RFC 9135 — Integrated Routing and Bridging in EVPN](https://tools.ietf.org/html/rfc9135)
