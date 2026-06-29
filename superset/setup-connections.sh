#!/usr/bin/env bash
# Registers the four IDS data sources in Superset via its REST API and
# validates each driver with test_connection first.
# Run from the host; Superset is published on :8089 (container :8088).
set -euo pipefail

BASE="http://localhost:8089"
JAR="$(mktemp)"

echo "==> login"
TOKEN=$(curl -s -c "$JAR" -X POST "$BASE/api/v1/security/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin","provider":"db","refresh":true}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

CSRF=$(curl -s -b "$JAR" -c "$JAR" "$BASE/api/v1/security/csrf_token/" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"])')

auth=(-H "Authorization: Bearer $TOKEN" -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json")

# name|sqlalchemy_uri  (hosts are compose service names, reachable from Superset)
sources=(
  "Cassandra (via Presto)|presto://presto:8080/cassandra"
  "MariaDB (personalities)|mysql+pymysql://ids_user:ids_password@mariadb:3306/user_personalities"
  "Hive (users)|hive://hive@hive:10000/default"
  "Druid (tweets)|druid://druid:8082/druid/v2/sql/"
)

for s in "${sources[@]}"; do
  name="${s%%|*}"; uri="${s#*|}"
  echo "==> test_connection: $name"
  body=$(python3 -c 'import json,sys;print(json.dumps({"database_name":sys.argv[1],"sqlalchemy_uri":sys.argv[2]}))' "$name" "$uri")
  resp=$(curl -s -b "$JAR" "${auth[@]}" -X POST "$BASE/api/v1/database/test_connection" -d "$body")
  if [ -z "$resp" ] || [ "$resp" = "null" ]; then
    echo "    OK"
  else
    echo "    -> $resp"
  fi
done

echo
echo "==> creating database connections"
for s in "${sources[@]}"; do
  name="${s%%|*}"; uri="${s#*|}"
  body=$(python3 -c 'import json,sys;print(json.dumps({"database_name":sys.argv[1],"sqlalchemy_uri":sys.argv[2],"expose_in_sqllab":True}))' "$name" "$uri")
  resp=$(curl -s -b "$JAR" "${auth[@]}" -X POST "$BASE/api/v1/database/" -d "$body")
  id=$(echo "$resp" | python3 -c 'import sys,json
try:
  d=json.load(sys.stdin); print("id="+str(d.get("id")) if d.get("id") else d)
except Exception as e:
  print(sys.stdin.read())' 2>/dev/null || echo "$resp")
  echo "  $name -> $id"
done

rm -f "$JAR"
