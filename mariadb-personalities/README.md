# mariadb-personalities

MariaDB image preloaded with the schema for the `user_personalities` database, containing MBTI personality labels linked to Twitter user IDs.

## Schema

**Database:** `user_personalities`

**Table:** `mbti_labels`

| Column | Type | Description |
|---|---|---|
| `id` | BIGINT (PK) | Twitter user ID |
| `mbti_personality` | VARCHAR(10) | MBTI type (e.g. `infp`, `entj`) |
| `pers_id` | INT | Personality numeric ID |

## Requirements

Place your `mbti_labels.csv` file inside a `./data` directory before starting:

```
mariadb-personalities/
├── data/
│   └── mbti_labels.csv
├── .env
└── docker-compose.yml
```

The CSV must have the following header:

```
id,mbti_personality,pers_id
```

## Environment variables

Copy `.env` and adjust values as needed:

| Variable | Default | Description |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `root` | Root password |
| `MYSQL_DATABASE` | `user_personalities` | Database name |
| `MYSQL_USER` | `ids_user` | App user |
| `MYSQL_PASSWORD` | `ids_password` | App user password |

## Usage

### Build and run

```bash
docker compose up -d
```

### Run standalone (without docker-compose)

```bash
docker run -d \
  --name mariadb_personalities \
  -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=user_personalities \
  -e MYSQL_USER=ids_user \
  -e MYSQL_PASSWORD=ids_password \
  -v $(pwd)/data:/var/lib/mysql-files/data:ro \
  -p 3306:3306 \
  <your-dockerhub-username>/mariadb-personalities:latest
```

## Utility scripts

All scripts are in `./bashs/` and connect to a running container named `mariadb_personalities`.

```bash
# Check total number of rows loaded
bash bashs/count-rows.sh

# Preview first 5 rows
bash bashs/fitst-5rows.sh

# Count users per MBTI personality
bash bashs/check-mbti-count.sh

# Inspect table structure
bash bashs/check-db-structure.sh
```

## Publishing to Docker Hub

```bash
# Build the image
docker build -t <your-dockerhub-username>/mariadb-personalities:latest .

# Push to Docker Hub
docker push <your-dockerhub-username>/mariadb-personalities:latest
```
