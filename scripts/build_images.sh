#!/usr/bin/env bash
# Build the local images used by evpn-lab.clab.yml (containerlab cannot build images).
# Idempotent: an image that already exists is skipped, pass --force to rebuild.
set -euo pipefail

cd "$(dirname "$0")/.."

# tag -> build context
declare -A IMAGES=(
    ["evpnlab/tac_plus-ng:latest"]="images/tac_plus-ng"
    ["evpnlab/network-multitool-8021x:latest"]="images/network-multitool-8021x"
)

force=no
[[ "${1:-}" == "--force" ]] && force=yes

for tag in "${!IMAGES[@]}"; do
    if [[ "$force" == no ]] && docker image inspect "$tag" >/dev/null 2>&1; then
        echo "skip  $tag (already built)"
        continue
    fi
    echo "build $tag"
    docker build -t "$tag" "${IMAGES[$tag]}"
done
