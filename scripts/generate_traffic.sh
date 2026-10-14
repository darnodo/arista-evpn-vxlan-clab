#!/usr/bin/env bash
# Generates L2 and L3 traffic at the same time with iperf3 and shows live
# bandwidth bars. Usage: generate_traffic.sh <duration_seconds>
#   L2: dc-server1 <-> dc-server3, VLAN 40 / VNI 110040, both directions (--bidir)
#   L3: DC -> Campus over VRF gold
# Refs #18.
set -euo pipefail

DURATION="${1:?Usage: $0 <duration_seconds>}"
if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || [[ "$DURATION" -lt 1 ]]; then
    echo "Duration must be a positive integer (seconds)" >&2
    exit 1
fi

LAB_PREFIX="clab-arista-evpn-fabric"
BAR_WIDTH=30

# name|server|server_ip|client|iperf3 option|port
# -R: data flows server -> client. --bidir: both directions at once.
FLOWS=(
    "l2|dc-server1|10.40.40.101|dc-server3|--bidir|5302"
    "l3a|dc-server2|10.34.34.102|campus-host1|-R|5301"
    "l3b|dc-server4|10.78.78.104|campus-host2|-R|5301"
)

# section|flow name|iperf3 log tag|label
# Tags: [RX-C] = server -> client, [TX-C] = client -> server (--bidir only)
ROWS=(
    "L2 VNI 110040 (VLAN 40)|l2|[RX-C]|dc-server1 ▶ dc-server3"
    "L2 VNI 110040 (VLAN 40)|l2|[TX-C]|dc-server3 ▶ dc-server1"
    "L3 VRF gold|l3a||dc-server2 ▶ campus-host1"
    "L3 VRF gold|l3b||dc-server4 ▶ campus-host2"
)

WORKDIR="$(mktemp -d)"
CLIENT_PIDS=()
MAX_MBIT=1

cleanup() {
    for pid in "${CLIENT_PIDS[@]:-}"; do
        kill "$pid" >/dev/null 2>&1 || true
    done
    for flow in "${FLOWS[@]}"; do
        IFS='|' read -r _ server _ _ _ port <<<"$flow"
        docker exec "${LAB_PREFIX}-${server}" pkill -f "iperf3 -s -p ${port}" >/dev/null 2>&1 || true
    done
    rm -rf "$WORKDIR"
    [[ -t 1 ]] && tput cnorm
    return 0
}
trap cleanup EXIT INT TERM

# Colors only when stdout is a terminal
if [[ -t 1 ]]; then
    BOLD="$(tput bold)"; GREEN="$(tput setaf 2)"; CYAN="$(tput setaf 6)"; RESET="$(tput sgr0)"
else
    BOLD=""; GREEN=""; CYAN=""; RESET=""
fi

# bar <value> <max> -> "████░░░░"
bar() {
    local filled=$(awk -v v="$1" -v m="$2" -v w="$BAR_WIDTH" 'BEGIN { n = int(v * w / m); if (n > w) n = w; print n }')
    local out=""
    for ((i = 0; i < BAR_WIDTH; i++)); do
        if ((i < filled)); then out+="█"; else out+="░"; fi
    done
    echo "$out"
}

# last_mbit <flow> <tag> -> last interval bandwidth in Mbits/sec (empty if none)
last_mbit() {
    grep -F "$2" "${WORKDIR}/$1.log" 2>/dev/null | grep 'Mbits/sec' | grep -v -E 'sender|receiver' | tail -1 |
        awk '{ for (i = 1; i <= NF; i++) if ($i == "Mbits/sec") print $(i - 1) }' || true
}

echo "Starting iperf3 servers..."
for flow in "${FLOWS[@]}"; do
    IFS='|' read -r _ server _ _ _ port <<<"$flow"
    docker exec -d "${LAB_PREFIX}-${server}" iperf3 -s -p "$port"
done
sleep 1

for flow in "${FLOWS[@]}"; do
    IFS='|' read -r name _ server_ip client opt port <<<"$flow"
    docker exec "${LAB_PREFIX}-${client}" iperf3 -c "$server_ip" -p "$port" "$opt" \
        -t "$DURATION" -i 1 --forceflush -f m >"${WORKDIR}/${name}.log" 2>&1 &
    CLIENT_PIDS+=("$!")
done

[[ -t 1 ]] && { tput civis; tput clear; }

for ((elapsed = 0; elapsed <= DURATION; elapsed++)); do
    [[ -t 1 ]] && tput home
    printf "%sEVPN/VXLAN lab traffic generator%s\n" "$BOLD" "$RESET"
    printf "[%s] %d/%ds\n" "$(bar "$elapsed" "$DURATION")" "$elapsed" "$DURATION"

    # Scale all bars on the highest rate seen so far
    section=""
    for row in "${ROWS[@]}"; do
        IFS='|' read -r sec name tag label <<<"$row"
        mbit="$(last_mbit "$name" "$tag")"
        if [[ -n "$mbit" ]] && awk -v v="$mbit" -v m="$MAX_MBIT" 'BEGIN { exit !(v > m) }'; then
            MAX_MBIT="$mbit"
        fi
        if [[ "$sec" != "$section" ]]; then
            printf "\n%s%s%s\n" "$CYAN" "$sec" "$RESET"
            section="$sec"
        fi
        if [[ -n "$mbit" ]]; then
            printf "  %-30s %s%s%s %8s Mbit/s\n" "$label" "$GREEN" "$(bar "$mbit" "$MAX_MBIT")" "$RESET" "$mbit"
        else
            printf "  %-30s %s waiting...\n" "$label" "$(bar 0 1)"
        fi
    done
    [[ -t 1 ]] && tput ed
    sleep 1
done

wait "${CLIENT_PIDS[@]}" 2>/dev/null || true

printf "\n%sSummary (receiver side)%s\n" "$BOLD" "$RESET"
for row in "${ROWS[@]}"; do
    IFS='|' read -r _ name tag label <<<"$row"
    line="$(grep -F "$tag" "${WORKDIR}/${name}.log" 2>/dev/null | grep receiver | tail -1 || true)"
    avg="$(awk '{ for (i = 1; i <= NF; i++) if ($i == "Mbits/sec") print $(i - 1) " Mbit/s" }' <<<"$line")"
    printf "  %-30s %s\n" "$label" "${avg:-no data}"
done
