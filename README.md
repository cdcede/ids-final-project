# IDS Twitter — Multi-source Analytics Platform

A self-contained, Docker-based platform that brings **four heterogeneous data
stores** together and visualizes them in a single **Apache Superset** dashboard.
It combines a real-time streaming pipeline (tweets) with relational and graph
stores (personalities, users, follow graph), exactly the "multiple data sources"
scenario the IDS project asks for.

```
                         ┌───────────────────────────────────────────┐
 STREAMING               │              BI / VISUALIZATION           │
 tweets1.json            │                                           │
   │ MQTT                │   ┌─────────┐        ┌──────────────────┐ │
   ▼                     │   │ presto  │◀──────▶│                  │ │
 mosquitto ─▶ kafka-connect ─▶ kafka ─▶ druid ──┼───native druid://─▶│                  │ │
                             (tweets-kafka)      │   │              │   Apache Superset │ │
 RELATIONAL                                      │   │ mysql://     │     (:8089)       │ │
 mariadb (mbti_labels) ──────────────────────────┼───────────────────▶│  4-chart         │ │
 hive    (users_data)  ──────────────────────────┼───native hive://──▶│  dashboard       │ │
                                                 │   │              │ │                  │ │
 GRAPH                                           │   │ presto://    │ │                  │ │
 cas1/cas2/cas3 (twitter.edges) ─────────────────┼─▶ presto ────────┼─▶│                  │ │
   ▲ loader (one-shot, RF=3)                     │   cassandra cat. │ └──────────────────┘ │
                                                 └───────────────────────────────────────┘
```

All services share the default Compose network, so they reach each other by
name (`kafka`, `druid`, `mariadb`, `hive`, `cas1`, `presto`, …).

## Data sources

| Domain | Store | Object | Rows | How Superset reads it |
| ------ | ----- | ------ | ---- | --------------------- |
| Streaming | **Druid** | `tweets-kafka` | live | native `druid://` (broker `:8082`) |
| Relational | **MariaDB** | `user_personalities.mbti_labels` | 8 328 | native `mysql+pymysql://` |
| Relational | **Hive** | `default.users_data` | 8 328 | native `hive://` |
| Graph | **Cassandra** | `twitter.edges` | 6 067 | **via PrestoDB** (`presto://`) |

> **Why Presto only for Cassandra?** Superset speaks SQL through SQLAlchemy
> dialects. Druid, MariaDB and Hive all have native dialects. Cassandra (CQL) is
> **not** SQL and has no maintained Superset dialect, so **PrestoDB** sits in
> front of it and exposes `twitter.edges` as plain SQL.

## Services

| Service | Image | Ports | Role |
| ------- | ----- | ----- | ---- |
| `zookeeper` | `confluentinc/cp-zookeeper:7.5.0` | 2181 (internal) | Kafka coordination |
| `kafka` | `confluentinc/cp-kafka:7.5.0` | 9092 | Message broker |
| `mosquitto` | `eclipse-mosquitto:2` | 1883 | MQTT broker |
| `kafka-connect` | `confluentinc/cp-kafka-connect:7.5.0` | 8083 | MQTT → Kafka bridge |
| `druid` | `jdvelasq/druid:0.22.1` | 8888, 8088, 9999, 50070 | Real-time analytics DB |
| `python-mqtt` | `cdcede/python-mqtt:1.0` | — | Tweet publisher |
| `init` | `curlimages/curl:8.11.0` | — | One-shot: registers connector + Druid supervisor |
| `mariadb` | `urtatsberrocal/mariadb-personalities:latest` | 3306 | MBTI personalities |
| `hive` | `iraida107/hive-users:latest` | 10000, 10002, 9083 | Users (HiveServer2) |
| `cas1`/`cas2`/`cas3` | `mikelez/ids-twitter-cassandra:latest` | 9042 (cas1) | 3-node / RF=3 follow graph |
| `cassandra-loader` | `mikelez/ids-twitter-cassandra:latest` | — | One-shot: creates schema + loads `edges` |
| `presto` | `prestodb/presto:latest` | 8080 | Cassandra → SQL bridge |
| `superset` | `ids-superset` (built) | **8089** | BI / dashboards |

> Superset is published on **8089** (its native `8088` collides with Druid).

## Prerequisites

- Docker + Docker Compose
- **~16 GB** allocated to Docker. The stack is memory-tight: three Cassandra
  nodes + Druid + Kafka + Presto + Superset. Below that, Cassandra nodes get
  OOM-killed (exit 137) on startup.
- `tweets1.json` (~200 MB) in the project root — **not tracked in git** (exceeds
  GitHub's 100 MB limit). The `python-mqtt` publisher mounts it read-only; without
  it the publisher won't start. Shape:
  ```json
  [ { "id": 12345, "tweets": ["first tweet", "second tweet", "..."] } ]
  ```

## Getting started

### 1. Bring up the whole stack

```bash
docker compose up -d --build
```

This builds the Superset image and starts everything. Two one-shot services run
automatically and then exit:

- **`init`** — registers the MQTT source connector and submits the Druid
  ingestion supervisor (`tweets-kafka`).
- **`cassandra-loader`** — after all three Cassandra nodes are healthy, creates
  the `twitter` keyspace (RF=3) and bulk-loads the 6 067 edges. **Required** —
  the image boots as a plain node and does *not* self-load.

First boot takes a few minutes (Cassandra nodes join one at a time via chained
healthchecks; Superset migrates its metadata DB).

### 2. Register the Superset connections + dashboard

```bash
bash superset/setup-connections.sh     # creates the 4 database connections
python3 superset/build-dashboard.py    # creates 4 datasets + charts + dashboard
```

Then open **http://localhost:8089** (login **`admin` / `admin`**) →
**Dashboards → IDS Twitter — Multi-source Dashboard**.

The dashboard (see `ids-dashboard.png`) shows:

1. **Tweets over time** — live stream from Druid
2. **MBTI distribution** — pie from MariaDB
3. **Users in follow graph** — 6 067, from Cassandra via Presto
4. **Total users (Hive)** — 8 328, from Hive

## Superset connection URIs

| Source | SQLAlchemy URI |
| ------ | -------------- |
| Cassandra (via Presto) | `presto://presto:8080/cassandra` |
| MariaDB | `mysql+pymysql://ids_user:ids_password@mariadb:3306/user_personalities` |
| Hive | `hive://hive@hive:10000/default` |
| Druid | `druid://druid:8082/druid/v2/sql/` |

> Hosts are Compose service names; Superset reaches them over the internal
> network, so Druid's `8082` works even though it is not published to the host.

## Verify the pipeline (optional)

```bash
# Cassandra via Presto -> 6067
docker exec presto presto-cli --server localhost:8080 \
  --catalog cassandra --schema twitter --execute "SELECT COUNT(*) FROM edges"

# MariaDB -> 8328
docker exec mariadb_personalities mariadb -uids_user -pids_password \
  user_personalities -N -e "SELECT COUNT(*) FROM mbti_labels;"

# Hive -> 8328
docker exec hive_users beeline -u "jdbc:hive2://localhost:10000/default" \
  -e "SELECT COUNT(*) FROM users_data;"

# Druid (broker SQL) -> live count
docker exec druid curl -s -X POST http://localhost:8082/druid/v2/sql/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"SELECT COUNT(*) AS c FROM \"tweets-kafka\""}'
```

## Project layout

```
.
├── compose.yaml                 # Unified stack (15 services)
├── connect-mqtt-source.json     # MQTT Source Connector config
├── druid-supervisor.json        # Druid Kafka ingestion supervisor spec
├── jars/                        # Connector plugins for Kafka Connect
├── python/                      # Source for cdcede/python-mqtt (tweet publisher)
├── mariadb-personalities/       # Source data + utility scripts for MariaDB/Hive
│   ├── data/                    #   mbti_labels.csv (mounted into MariaDB)
│   └── users1.json/             #   users payload (mounted into Hive)
├── presto/
│   └── cassandra.properties     # Presto "cassandra" catalog (cas1,cas2,cas3:9042)
├── superset/
│   ├── Dockerfile               # apache/superset + presto/hive/mysql/druid drivers
│   ├── superset-bootstrap.sh    # First-boot: migrate DB, create admin, serve
│   ├── setup-connections.sh     # Registers the 4 database connections (REST API)
│   └── build-dashboard.py       # Builds datasets + charts + dashboard (REST API)
├── tweets1.json                 # Source dataset (not tracked; provide your own)
└── ids-dashboard.png            # Screenshot of the final dashboard
```

## Stopping

```bash
docker compose down       # stop everything, keep volumes (data + Superset state)
docker compose down -v    # also wipe volumes (Cassandra data, Superset dashboards)
```
