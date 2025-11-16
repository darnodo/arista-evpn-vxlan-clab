# Quick Reference Guide

Quick commands and references for the Arista EVPN-VXLAN lab.

## Quick Start

```bash
# Deploy lab
sudo containerlab deploy -t evpn-lab.clab.yml

# Check status
sudo containerlab inspect -t evpn-lab.clab.yml

# Destroy lab
sudo containerlab destroy -t evpn-lab.clab.yml
```

## Using Helper Scripts

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Interactive deployment menu
sudo ./scripts/deploy.sh

# Direct commands
sudo ./scripts/deploy.sh deploy
sudo ./scripts/deploy.sh status
sudo ./scripts/deploy.sh validate

# Test connectivity
sudo bash scripts/test-connectivity.sh

# Cleanup
sudo bash scripts/cleanup.sh
```

## Device Access

### SSH Access
```bash
ssh admin@clab-arista-evpn-fabric-spine1
ssh admin@clab-arista-evpn-fabric-leaf1
# Password: admin
```

### Docker Exec
```bash
docker exec -it clab-arista-evpn-fabric-spine1 Cli
docker exec -it clab-arista-evpn-fabric-leaf1 Cli
```

## Management IPs

| Device  | Management IP  | Loopback0      | Loopback1     |
|---------|---------------|----------------|---------------|
| spine1  | 172.16.0.1    | 10.0.250.1     | N/A           |
| spine2  | 172.16.0.2    | 10.0.250.2     | N/A           |
| leaf1   | 172.16.0.25   | 10.0.250.11    | 10.0.255.11   |
| leaf2   | 172.16.0.50   | 10.0.250.12    | 10.0.255.11   |
| leaf3   | 172.16.0.27   | 10.0.250.13    | 10.0.255.12   |
| leaf4   | 172.16.0.28   | 10.0.250.14    | 10.0.255.12   |
| leaf5   | 172.16.0.29   | 10.0.250.15    | 10.0.255.13   |
| leaf6   | 172.16.0.30   | 10.0.250.16    | 10.0.255.13   |
| leaf7   | 172.16.0.31   | 10.0.250.17    | 10.0.255.14   |
| leaf8   | 172.16.0.32   | 10.0.250.18    | 10.0.255.14   |

## AS Numbers

| Device Pair | AS Number |
|------------|-----------|
| Spines     | 65000     |
| Leaf1/2    | 65001     |
| Leaf3/4    | 65002     |
| Leaf5/6    | 65003     |
| Leaf7/8    | 65004     |

## VNI Mapping

| VLAN/VRF | VNI    | Type | VTEPs    |
|----------|--------|------|----------|
| VLAN 40  | 110040 | L2   | 1, 3     |
| VRF gold | 100001 | L3   | 2, 4     |
| VLAN 34  | -      | L3   | 2        |
| VLAN 78  | -      | L3   | 4        |

## Essential Show Commands

### Quick Status Check
```bash
show ip interface brief
show bgp summary
show bgp evpn summary
show mlag
show vxlan vtep
```

### Detailed Verification
```bash
# Underlay
show ip bgp
show ip route
show bgp ipv4 unicast summary

# Overlay
show bgp evpn
show bgp evpn route-type mac-ip
show bgp evpn route-type ip-prefix ipv4

# VXLAN
show interface vxlan1
show vxlan address-table
show vxlan vni
show vxlan config-sanity

# MLAG
show mlag detail
show mlag interfaces
show port-channel summary

# VRF
show vrf
show ip route vrf gold
show bgp ipv4 unicast vrf gold summary
```

## Common Troubleshooting Commands

```bash
# Check BGP neighbors
show ip bgp neighbors <ip>
show bgp evpn neighbors <ip>

# Check routes
show ip route detail
show bgp evpn detail

# Check counters
show interfaces counters errors
show vxlan counters

# Check logs
show logging
show logging last 50

# Packet capture
bash tcpdump -i et11 -n port 179
bash tcpdump -i et11 -n port 4789
```

## Configuration Snippets

### Save Configuration
```bash
write memory
# or
copy running-config startup-config
```

### View Configuration
```bash
show running-config
show running-config | section bgp
show running-config | section vxlan
```

### Enable Configuration Mode
```bash
enable
configure terminal
```

## Testing Connectivity

### From Leaf Devices
```bash
# Ping loopbacks
ping 10.0.250.1
ping 10.0.255.13

# Ping in VRF
ping vrf gold 10.78.78.1

# Traceroute
traceroute 10.0.255.14
traceroute vrf gold 10.34.34.1
```

### From Host Containers
```bash
# Enter host container
docker exec -it clab-arista-evpn-fabric-host1 sh

# Test connectivity
ping 10.40.40.1
```

## Performance Monitoring

```bash
# Interface statistics
show interfaces ethernet 11 counters
show interfaces ethernet 11 counters rate

# BGP statistics
show bgp evpn summary
show bgp evpn route-type mac-ip | count

# System resources
show processes top
show version
```

## Useful Filters

```bash
# Grep examples
show bgp evpn summary | grep Estab
show interfaces status | include up
show running-config | section vxlan

# JSON output (for automation)
show bgp evpn summary | json
show interfaces status | json
```

## Lab Topology Reference

```
                Spine1 -------- Spine2
                  |               |
        +---------+-----------+---+----------+
        |         |           |              |
    Leaf1/2   Leaf3/4     Leaf5/6       Leaf7/8
    (VTEP1)   (VTEP2)     (VTEP3)       (VTEP4)
       |         |           |              |
    Host1     Host2       Host3          Host4
```

## Feature Matrix

| Feature          | VTEP1 | VTEP2 | VTEP3 | VTEP4 |
|------------------|-------|-------|-------|-------|
| L2 VXLAN (VLAN40)| ✓     | -     | ✓     | -     |
| L3 VXLAN (VRF)   | -     | ✓     | -     | ✓     |
| BGP Border       | -     | -     | -     | ✓     |
| MLAG             | ✓     | ✓     | ✓     | ✓     |

## Keyboard Shortcuts (CLI)

```
Ctrl+Z  - Exit to privileged EXEC mode
Ctrl+C  - Interrupt current command
Tab     - Command completion
?       - Context-sensitive help
```

## Reset to Factory

```bash
# Erase startup config
enable
bash sudo /mnt/flash/zerotouch reset

# Or manually
enable
write erase
reload
```

## Additional Resources

- Full documentation: `docs/`
- Validation commands: `docs/validation-commands.md`
- Configuration guide: `docs/configuration-guide.md`
- Helper scripts: `scripts/`

## Support

For issues or questions:
- Check logs: `show logging`
- Review documentation in `docs/` directory
- Original blog post: https://overlaid.net/2019/01/27/arista-bgp-evpn-configuration-example/

---

**Tip**: Bookmark this page for quick reference during lab work!
