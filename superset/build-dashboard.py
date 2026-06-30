#!/usr/bin/env python3
"""Build the IDS dashboard in Superset via its REST API (stdlib only).

Creates the four datasets (if missing) on top of the four database
connections, then builds one chart per source and a dashboard laying them
out together:
  Cassandra (via Presto)  -> twitter.edges                 -> "Users in follow graph"
  MariaDB (personalities) -> user_personalities.mbti_labels -> "MBTI distribution"
  Hive (users)            -> default.users_data            -> "Total users (Hive)"
  Druid (tweets)          -> druid."tweets-kafka"          -> "Tweets over time"

Prerequisite: the four database *connections* must already exist
(run superset/setup-connections.sh first). The *datasets* are created here,
so this is safe to run on a fresh stack. Dataset creation is idempotent
(find-or-create by name). A source whose table is not yet queryable
(e.g. Druid before any tweets have streamed) is skipped with a warning
instead of aborting the whole build.
"""
import json
import urllib.request
import urllib.error
import http.cookiejar

BASE = "http://localhost:8089"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def call(method, path, token=None, csrf=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if csrf:
        req.add_header("X-CSRFToken", csrf)
    with opener.open(req) as r:
        return json.loads(r.read().decode())


token = call("POST", "/api/v1/security/login",
             body={"username": "admin", "password": "admin",
                   "provider": "db", "refresh": True})["access_token"]
csrf = call("GET", "/api/v1/security/csrf_token/", token=token)["result"]


# ---- datasets -------------------------------------------------------------
# (database connection name, schema, table) for each source.
SOURCES = [
    ("Cassandra (via Presto)",  "twitter",            "edges"),
    ("MariaDB (personalities)", "user_personalities", "mbti_labels"),
    ("Hive (users)",            "default",            "users_data"),
    ("Druid (tweets)",          "druid",              "tweets-kafka"),
]

# database connection name -> id (must already exist; created by setup-connections.sh)
databases = {d["database_name"]: d["id"]
             for d in call("GET", "/api/v1/database/", token=token)["result"]}
# (db_id, schema, table) -> existing dataset id
existing = {(d["database"]["id"], d.get("schema") or "", d["table_name"]): d["id"]
            for d in call("GET", "/api/v1/dataset/", token=token)["result"]}


def ensure_dataset(db_name, schema, table):
    """Return the dataset id for (db_name, schema, table), creating it if
    needed. Returns None if the connection or table is not (yet) available."""
    if db_name not in databases:
        print(f"  ! database '{db_name}' not found — run setup-connections.sh first; skipping")
        return None
    db = databases[db_name]
    key = (db, schema or "", table)
    if key in existing:
        print(f"  dataset {schema}.{table} already exists -> id {existing[key]}")
        return existing[key]
    try:
        did = call("POST", "/api/v1/dataset/", token=token, csrf=csrf,
                   body={"database": db, "schema": schema, "table_name": table})["id"]
        print(f"  dataset {schema}.{table} created -> id {did}")
        return did
    except urllib.error.HTTPError as e:
        print(f"  ! could not create dataset {schema}.{table} "
              f"(HTTP {e.code}: table not queryable yet) — skipping its chart")
        return None


print("==> datasets")
ds = {}  # database name -> dataset id (only for sources that exist)
for db_name, schema, table in SOURCES:
    did = ensure_dataset(db_name, schema, table)
    if did is not None:
        ds[db_name] = did


def count_metric(label):
    return {"expressionType": "SQL", "sqlExpression": "COUNT(*)", "label": label}


def make_chart(name, ds_id, viz, params):
    params = {"datasource": f"{ds_id}__table", "viz_type": viz, **params}
    body = {"slice_name": name, "viz_type": viz,
            "datasource_id": ds_id, "datasource_type": "table",
            "params": json.dumps(params)}
    cid = call("POST", "/api/v1/chart/", token=token, csrf=csrf, body=body)["id"]
    print(f"  chart '{name}' -> id {cid}")
    return cid


# ---- charts: one per source that has a dataset ----------------------------
# (database name, chart name, viz type, params)
CHART_SPECS = [
    ("Druid (tweets)", "Tweets over time", "echarts_timeseries_line", {
        "x_axis": "__time", "time_grain_sqla": "PT1M",
        "metrics": [count_metric("tweets")], "groupby": [],
        "row_limit": 10000, "adhoc_filters": []}),
    ("MariaDB (personalities)", "MBTI distribution", "pie", {
        "groupby": ["mbti_personality"], "metric": count_metric("count"),
        "row_limit": 100, "adhoc_filters": []}),
    ("Cassandra (via Presto)", "Users in follow graph", "big_number_total", {
        "metric": count_metric("graph users"), "adhoc_filters": []}),
    ("Hive (users)", "Total users (Hive)", "big_number_total", {
        "metric": count_metric("users"), "adhoc_filters": []}),
]

print("==> charts")
charts = []  # list of (chart_id, chart_name)
for db_name, name, viz, params in CHART_SPECS:
    if db_name not in ds:
        print(f"  - skipping '{name}' (no dataset for {db_name})")
        continue
    charts.append((make_chart(name, ds[db_name], viz, params), name))

if not charts:
    raise SystemExit("No datasets available — nothing to build. "
                     "Run setup-connections.sh and make sure the stack is up.")

# ---- assemble dashboard layout (2 charts per row) -------------------------
pos = {
    "DASHBOARD_VERSION_KEY": "v2",
    "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
    "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
    "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID",
                  "meta": {"text": "IDS Twitter — Multi-source Dashboard"}},
}
NCOLS = 2
for i in range(0, len(charts), NCOLS):
    rid = f"ROW-{i // NCOLS + 1}"
    pos["GRID_ID"]["children"].append(rid)
    cells = []
    pos[rid] = {"type": "ROW", "id": rid, "children": cells,
                "parents": ["ROOT_ID", "GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"}}
    for j, (cid, cname) in enumerate(charts[i:i + NCOLS]):
        cell = f"CHART-{i + j + 1}"
        cells.append(cell)
        pos[cell] = {"type": "CHART", "id": cell, "children": [],
                     "parents": ["ROOT_ID", "GRID_ID", rid],
                     "meta": {"chartId": cid, "width": 6, "height": 50,
                              "sliceName": cname}}

dash = call("POST", "/api/v1/dashboard/", token=token, csrf=csrf, body={
    "dashboard_title": "IDS Twitter — Multi-source Dashboard",
    "position_json": json.dumps(pos),
    "published": True,
})["id"]
print(f"dashboard -> id {dash}")

# link charts to the dashboard so they belong to it
for cid, _ in charts:
    call("PUT", f"/api/v1/chart/{cid}", token=token, csrf=csrf,
         body={"dashboards": [dash]})

print(f"DONE -> {BASE}/superset/dashboard/{dash}/")
