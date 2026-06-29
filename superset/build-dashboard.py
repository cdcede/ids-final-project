#!/usr/bin/env python3
"""Build the IDS dashboard in Superset via its REST API (stdlib only).

Assumes the four databases (ids 1-4) and datasets (ids 1-4) already exist:
  1 Cassandra (via Presto)  -> dataset 1  twitter.edges
  2 MariaDB (personalities) -> dataset 2  user_personalities.mbti_labels
  3 Hive (users)            -> dataset 3  default.users_data
  4 Druid (tweets)          -> dataset 4  druid."tweets-kafka"
"""
import json
import urllib.request
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


charts = []
# 1) Druid — tweets over time (live stream)
charts.append((make_chart(
    "Tweets over time", 4, "echarts_timeseries_line", {
        "x_axis": "__time", "time_grain_sqla": "PT1M",
        "metrics": [count_metric("tweets")], "groupby": [],
        "row_limit": 10000, "adhoc_filters": []}), "Tweets over time"))

# 2) MariaDB — MBTI personality distribution
charts.append((make_chart(
    "MBTI distribution", 2, "pie", {
        "groupby": ["mbti_personality"], "metric": count_metric("count"),
        "row_limit": 100, "adhoc_filters": []}), "MBTI distribution"))

# 3) Cassandra (via Presto) — total users in the follow graph
charts.append((make_chart(
    "Users in follow graph", 1, "big_number_total", {
        "metric": count_metric("graph users"), "adhoc_filters": []}),
    "Users in follow graph"))

# 4) Hive — total users
charts.append((make_chart(
    "Total users (Hive)", 3, "big_number_total", {
        "metric": count_metric("users"), "adhoc_filters": []}),
    "Total users (Hive)"))

# ---- assemble dashboard layout (2 rows x 2 charts) -------------------------
pos = {
    "DASHBOARD_VERSION_KEY": "v2",
    "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
    "GRID_ID": {"type": "GRID", "id": "GRID_ID",
                "children": ["ROW-1", "ROW-2"], "parents": ["ROOT_ID"]},
    "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID",
                  "meta": {"text": "IDS Twitter — Multi-source Dashboard"}},
}
rows = [["R1C1", "R1C2"], ["R2C1", "R2C2"]]
for ri, row in enumerate(rows, 1):
    rid = f"ROW-{ri}"
    pos[rid] = {"type": "ROW", "id": rid, "children": row,
                "parents": ["ROOT_ID", "GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"}}
    for ci, cell in enumerate(row):
        cid, cname = charts[(ri - 1) * 2 + ci]
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
