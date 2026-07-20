#!/usr/bin/env bash
# Generates DC<->Campus traffic over VRF gold using iperf3 (bundled in the
# network-multitool image every host container runs), with a live
# server/client bandwidth dashboard. Refs #55.
set -euo pipefail

DURATION="${1:?Usage: $0 <duration_seconds>}"
if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || [[ "$DURATION" -lt 1 ]]; then
    echo "Duration must be a positive integer (seconds)" >&2
    exit 1
fi

LAB_PREFIX="clab-arista-evpn-fabric"
PORT=5301

# server_name:server_ip:client_name  — gold VRF pairs, stitched EVPN
# Type-5 path DC -> Core -> Campus (see README Host Addressing table)
PAIRS=(
    "dc-server2:10.34.34.102:campus-host1"
    "dc-server4:10.78.78.104:campus-host2"
)

WORKDIR="$(mktemp -d)"
CLIENT_PIDS=()

cleanup() {
    for pid in "${CLIENT_PIDS[@]:-}"; do
        kill "$pid" >/dev/null 2>&1 || true
    done
    for pair in "${PAIRS[@]}"; do
        IFS=':' read -r server _ _ <<<"$pair"
        docker exec "${LAB_PREFIX}-${server}" pkill -f "iperf3 -s -p ${PORT}" >/dev/null 2>&1 || true
    done
    rm -rf "$WORKDIR"
}
trap cleanup EXIT INT TERM

echo "Starting iperf3 servers..."
for pair in "${PAIRS[@]}"; do
    IFS=':' read -r server server_ip _ <<<"$pair"
    docker exec -d "${LAB_PREFIX}-${server}" iperf3 -s -p "$PORT"
done
sleep 1

echo "Starting iperf3 clients for ${DURATION}s..."
for pair in "${PAIRS[@]}"; do
    IFS=':' read -r server server_ip client <<<"$pair"
    logfile="${WORKDIR}/${client}.log"
    # -R: DC hosts the service, campus is the consumer -- data should flow
    # server -> client (download), not client -> server, to match how a
    # real DC-hosted service/campus-consumer pair behaves.
    docker exec "${LAB_PREFIX}-${client}" iperf3 -c "$server_ip" -p "$PORT" -R \
        -t "$DURATION" -i 1 --forceflush -f m >"$logfile" 2>&1 &
    CLIENT_PIDS+=("$!")
done

for ((elapsed = 0; elapsed <= DURATION; elapsed++)); do
    clear
    echo "EVPN/VXLAN lab traffic generator — ${elapsed}/${DURATION}s"
    echo
    echo "Servers (iperf3 -s):"
    for pair in "${PAIRS[@]}"; do
        IFS=':' read -r server server_ip _ <<<"$pair"
        echo "  ${server} (${server_ip}:${PORT})"
    done
    echo
    echo "Clients (live bandwidth):"
    for pair in "${PAIRS[@]}"; do
        IFS=':' read -r server server_ip client <<<"$pair"
        logfile="${WORKDIR}/${client}.log"
        last_line="$(grep -E 'Mbits/sec' "$logfile" 2>/dev/null | tail -1 || true)"
        bw="$(sed -E 's/.*[[:space:]]([0-9.]+ Mbits\/sec).*/\1/' <<<"$last_line")"
        [[ -z "$last_line" ]] && bw="waiting..."
        printf "  %-13s -> %-13s : %s\n" "$server" "$client" "$bw"
    done
    sleep 1
done

wait "${CLIENT_PIDS[@]}" 2>/dev/null || true

echo
echo "Done. Summary:"
for pair in "${PAIRS[@]}"; do
    IFS=':' read -r server _ client <<<"$pair"
    logfile="${WORKDIR}/${client}.log"
    summary="$(grep -E 'receiver' "$logfile" 2>/dev/null || true)"
    echo "  ${server} -> ${client}: ${summary:-no data}"
done
