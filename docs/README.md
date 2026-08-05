# Documentation Index

## Architecture

- [Overview](architecture/overview.md) — zones, design choices, node inventory, AS numbering, access switches
- [Addressing](architecture/addressing.md) — management, Loopback0, Loopback1, underlay P2P, host addressing
- [Control Plane](architecture/control-plane.md) — BGP/OSPF matrix per segment
- [VXLAN](architecture/vxlan.md) — L2/L3 VNI mapping, VRF `gold`, RD convention

## Operations

- [Deploy](operations/deploy.md) — prerequisites, cEOS import, deploy, access, cleanup
- [Validation](operations/validation.md) — end-to-end test procedures
- [Troubleshooting](operations/troubleshooting.md) — bottom-up diagnostic guide

## Observability

- [gnmic](observability/gnmic.md) — gNMI subscriptions
- [Prometheus](observability/prometheus.md) — scrape config, label relabeling
- [Weathermap](observability/weathermap.md) — dashboard-as-code panel generation
