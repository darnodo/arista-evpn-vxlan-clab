#!/bin/bash
# Connectivity test script for Arista EVPN-VXLAN lab

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local device="$2"
    local command="$3"
    local expected="$4"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    print_test "$test_name"
    
    if output=$(docker exec "clab-arista-evpn-fabric-$device" Cli -p 15 -c "$command" 2>&1); then
        if echo "$output" | grep -q "$expected"; then
            print_pass "$test_name"
            TESTS_PASSED=$((TESTS_PASSED + 1))
            return 0
        else
            print_fail "$test_name - Expected pattern not found"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            return 1
        fi
    else
        print_fail "$test_name - Command failed"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "========================================="
echo " EVPN-VXLAN Connectivity Tests"
echo "========================================="
echo ""

# Test 1: BGP Underlay - Spine to Leaf
echo "--- Testing BGP Underlay ---"
run_test "Spine1 BGP IPv4 neighbors" "spine1" "show bgp ipv4 unicast summary" "Estab"
run_test "Spine2 BGP IPv4 neighbors" "spine2" "show bgp ipv4 unicast summary" "Estab"
run_test "Leaf1 BGP IPv4 neighbors" "leaf1" "show bgp ipv4 unicast summary" "Estab"
echo ""

# Test 2: BGP EVPN Overlay
echo "--- Testing BGP EVPN Overlay ---"
run_test "Spine1 BGP EVPN neighbors" "spine1" "show bgp evpn summary" "Estab"
run_test "Spine2 BGP EVPN neighbors" "spine2" "show bgp evpn summary" "Estab"
run_test "Leaf1 BGP EVPN neighbors" "leaf1" "show bgp evpn summary" "Estab"
run_test "Leaf3 BGP EVPN neighbors" "leaf3" "show bgp evpn summary" "Estab"
echo ""

# Test 3: Loopback Reachability
echo "--- Testing Loopback Reachability ---"
run_test "Leaf1 can reach Spine1 loopback" "leaf1" "ping 10.0.250.1 repeat 3" "3 received"
run_test "Leaf1 can reach Spine2 loopback" "leaf1" "ping 10.0.250.2 repeat 3" "3 received"
run_test "Leaf1 can reach Leaf3 loopback" "leaf1" "ping 10.0.250.13 repeat 3" "3 received"
echo ""

# Test 4: MLAG Status
echo "--- Testing MLAG ---"
run_test "Leaf1 MLAG state" "leaf1" "show mlag" "Active"
run_test "Leaf2 MLAG state" "leaf2" "show mlag" "Active"
run_test "Leaf3 MLAG state" "leaf3" "show mlag" "Active"
run_test "Leaf4 MLAG state" "leaf4" "show mlag" "Active"
echo ""

# Test 5: VXLAN Interface
echo "--- Testing VXLAN ---"
run_test "Leaf1 VXLAN interface" "leaf1" "show interface vxlan1" "line protocol is up"
run_test "Leaf3 VXLAN interface" "leaf3" "show interface vxlan1" "line protocol is up"
run_test "Leaf5 VXLAN interface" "leaf5" "show interface vxlan1" "line protocol is up"
run_test "Leaf7 VXLAN interface" "leaf7" "show interface vxlan1" "line protocol is up"
echo ""

# Test 6: VXLAN VTEPs Discovery
echo "--- Testing VTEP Discovery ---"
run_test "Leaf1 discovers remote VTEPs" "leaf1" "show vxlan vtep" "10.0.255"
run_test "Leaf3 discovers remote VTEPs" "leaf3" "show vxlan vtep" "10.0.255"
run_test "Leaf5 discovers remote VTEPs" "leaf5" "show vxlan vtep" "10.0.255"
echo ""

# Test 7: EVPN Routes
echo "--- Testing EVPN Routes ---"
run_test "Leaf1 has EVPN Type-2 routes" "leaf1" "show bgp evpn route-type mac-ip" "RD:"
run_test "Leaf3 has EVPN Type-5 routes" "leaf3" "show bgp evpn route-type ip-prefix ipv4" "RD:"
run_test "Leaf7 has EVPN Type-5 routes" "leaf7" "show bgp evpn route-type ip-prefix ipv4" "RD:"
echo ""

# Test 8: VRF Routing
echo "--- Testing VRF Routing ---"
run_test "Leaf3 VRF gold exists" "leaf3" "show vrf" "gold"
run_test "Leaf3 has routes in VRF gold" "leaf3" "show ip route vrf gold" "10."
run_test "Leaf7 VRF gold exists" "leaf7" "show vrf" "gold"
run_test "Leaf7 has routes in VRF gold" "leaf7" "show ip route vrf gold" "10."
echo ""

# Test 9: VRF Connectivity
echo "--- Testing VRF Connectivity ---"
run_test "Leaf3 can reach Leaf7 in VRF gold" "leaf3" "ping vrf gold 10.78.78.1 repeat 3" "received"
run_test "Leaf7 can reach Leaf3 in VRF gold" "leaf7" "ping vrf gold 10.34.34.1 repeat 3" "received"
echo ""

# Test 10: ECMP Paths
echo "--- Testing ECMP ---"
run_test "Leaf1 has ECMP to remote loopbacks" "leaf1" "show ip route 10.0.250.13" "via"
echo ""

# Summary
echo "========================================="
echo " Test Summary"
echo "========================================="
echo "Total Tests Run: $TESTS_RUN"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo "========================================="

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check the output above.${NC}"
    exit 1
fi
