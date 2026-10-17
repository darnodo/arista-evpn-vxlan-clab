#!/usr/bin/env bash
# Set up the in-lab NetMapper after `containerlab deploy`, then crawl the lab.
# Idempotent: bucket, keys, database roles and API token are created once and
# kept; every run starts a new crawl and waits for its graph.
set -euo pipefail

cd "$(dirname "$0")/.."

LAB=clab-arista-evpn-fabric
GARAGE_ADMIN=http://172.16.0.79:3903
GARAGE_ADMIN_TOKEN=evpnlab-garage-admin
API=http://172.16.0.82:8080
TOKEN_FILE=$LAB/netmapper/token
SUPERUSER_DSN='postgres://netmapper:evpnlab-netmapper-db@172.16.0.78:5432/netmapper?sslmode=disable'
OPERATOR_DSN='postgres://nm_operator:evpnlab-nm-operator@172.16.0.78:5432/netmapper?sslmode=disable'
# S3 keys, must match the env of netmapper-collector / netmapper-api in evpn-lab.clab.yml
COLLECTOR_KEY=GK6e6d636f6c6c6563746f7231
COLLECTOR_SECRET=89a0abb4b39673dfb937a0340e4771d4ce5be92dcd1feaa18a0a655d8428becb
API_KEY=GK6e6d61706972656164657231
API_SECRET=cbd64fbdf8cb63d2e3a01fa2f648d5f6ee19e2f71892f0ab1a8b3c43bcae49a4

NM_IMAGE=$(docker inspect -f '{{.Config.Image}}' "$LAB-netmapper-engine")

# One-shot netmapper subcommand. Not `docker exec` into the engine: it crash-loops until
# its database login exists. Shares netmapper-db's network namespace, so it takes no mgmt IP.
nm() {
    docker run --rm --network "container:$LAB-netmapper-db" -e NETMAPPER_DSN="$1" \
        -v "$PWD/configs/netmapper/netmapper.yaml:/etc/netmapper/netmapper.yaml:ro" \
        "$NM_IMAGE" "${@:2}"
}
garage() {
    curl -sf -H "Authorization: Bearer $GARAGE_ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$GARAGE_ADMIN/v2/$1" ${2:+-d "$2"}
}
psql_db() { docker exec -i "$LAB-netmapper-db" psql -v ON_ERROR_STOP=1 -qtA -U netmapper -d netmapper "$@"; }
api() { curl -sf -H "Authorization: Bearer $(cat "$TOKEN_FILE")" "$API/v1/$1"; }
wait_for() {  # wait_for <what> <seconds> <command...>
    local what=$1 timeout=$2; shift 2
    for _ in $(seq "$timeout"); do "$@" >/dev/null 2>&1 && return 0; sleep 1; done
    echo "timeout waiting for $what" >&2; exit 1
}

# 1. Object store: single-node layout, bucket, collector key (read/write), API key (read only)
wait_for "garage admin API" 60 garage GetClusterStatus
if [[ "$(garage GetClusterLayout | jq '.roles | length')" == 0 ]]; then
    node=$(garage GetClusterStatus | jq -r '.nodes[0].id')
    version=$(garage GetClusterLayout | jq '.version')
    garage UpdateClusterLayout "{\"roles\":[{\"id\":\"$node\",\"zone\":\"lab\",\"capacity\":1000000000,\"tags\":[]}]}" >/dev/null
    garage ApplyClusterLayout "{\"version\":$((version + 1))}" >/dev/null
    echo "garage: layout applied"
fi
garage "GetBucketInfo?globalAlias=netmapper" >/dev/null || garage CreateBucket '{"globalAlias":"netmapper"}' >/dev/null
bucket=$(garage "GetBucketInfo?globalAlias=netmapper" | jq -r '.id')
for key in "$COLLECTOR_KEY:$COLLECTOR_SECRET:nm-collector:true" "$API_KEY:$API_SECRET:nm-api:false"; do
    IFS=: read -r id secret name write <<<"$key"
    garage "GetKeyInfo?id=$id" >/dev/null ||
        garage ImportKey "{\"accessKeyId\":\"$id\",\"secretAccessKey\":\"$secret\",\"name\":\"$name\"}" >/dev/null
    garage AllowBucketKey "{\"bucketId\":\"$bucket\",\"accessKeyId\":\"$id\",\"permissions\":{\"read\":true,\"write\":$write,\"owner\":false}}" >/dev/null
done
echo "garage: bucket netmapper ready"

# 2. Database: schema (migrate is idempotent), then one login per process
wait_for "postgres" 60 nm "$SUPERUSER_DSN" migrate
existing=$(psql_db -c "SELECT count(*) FROM pg_roles WHERE rolname IN ('nm_engine','nm_collector','nm_api','nm_operator')")
if [[ "$existing" != 4 ]]; then
    psql_db <<'SQL'
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT * FROM (VALUES
        ('nm_engine',    'netmapper_engine',    'evpnlab-nm-engine'),
        ('nm_collector', 'netmapper_collector', 'evpnlab-nm-collector'),
        ('nm_api',       'netmapper_api',       'evpnlab-nm-api'),
        ('nm_operator',  'netmapper_operator',  'evpnlab-nm-operator')
    ) AS t(login, grp, pw) LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.login) THEN
            EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L IN ROLE %I', r.login, r.pw, r.grp);
        END IF;
    END LOOP;
END $$;
SQL
    # the processes started before their login existed
    docker restart "$LAB-netmapper-engine" "$LAB-netmapper-collector" "$LAB-netmapper-api" >/dev/null
    echo "postgres: process logins created, NetMapper processes restarted"
fi

# 3. API token, read scope, kept in the lab directory (gone with `containerlab destroy`, like the DB)
if [[ ! -s "$TOKEN_FILE" ]]; then
    mkdir -p "$(dirname "$TOKEN_FILE")"
    nm "$OPERATOR_DSN" token create --name "weathermap-$(date +%Y%m%d%H%M%S)" --scope read >"$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    echo "api: token written to $TOKEN_FILE"
fi
wait_for "netmapper api" 60 curl -so /dev/null "$API/v1/snapshots"

# 4. Crawl, then wait for the new snapshot's graph
last=$(api snapshots | jq '[.snapshots[].id] | max // 0')
job=$(nm "$OPERATOR_DSN" run --config /etc/netmapper/netmapper.yaml --perimeter evpn-lab --seed-set spines)
echo "crawl: job $job started"
new_graph() { api snapshots | jq -e --argjson last "$last" 'any(.snapshots[]; .id > $last and .has_graph)'; }
wait_for "crawl graph" 300 new_graph
api devices | jq -r '"crawl: snapshot \(.snapshot.id), verdict \(.snapshot.verdict), \(.devices | length) devices"'
