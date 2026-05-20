# Davao Jeepney Route Optimization

A full data engineering and data science project analyzing commuter patterns across Davao City's jeepney routes — built on a lightweight data lakehouse with Docker and Python.

---

![alt text](assets/image.png)

## What this project does

- **Ingests** 1,100,000+ synthetic jeepney trip records and 5,000 passenger surveys through a FastAPI Bronze layer into MinIO (Parquet)
- **Transforms** raw data through a three-layer dbt pipeline (staging → intermediate → marts) in PostgreSQL
- **Clusters** commuters into 5 segments using K-Means (Student, Market Worker, CBD Worker, Underserved, Occasional)
- **Runs an A/B experiment** simulating a direct Matina → SM Lanang express route for the worst-served cluster
- **Surfaces insights** through Apache Superset dashboards and a Streamlit data science app

---

## Stack

| Layer                     | Tool                                   |
| ------------------------- | -------------------------------------- |
| Object storage (Bronze)   | MinIO                                  |
| Warehouse (Silver / Gold) | PostgreSQL 15                          |
| Ingestion API             | FastAPI + Pydantic v2                  |
| Transformation            | dbt-core 1.7 + dbt-postgres            |
| Orchestration             | Apache Airflow 3.2.1 (CeleryExecutor)  |
| BI dashboards             | Apache Superset 3.0                    |
| DS app                    | Streamlit                              |
| ML                        | scikit-learn (K-Means, DBSCAN) + scipy |
| Query engine              | DuckDB                                 |
| Task broker               | Redis 7.2                              |
| DB admin                  | pgAdmin 4                              |

---

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin) with at least **4 GB RAM** and **10 GB disk** allocated
- No other services running on ports `5432`, `5050`, `6379`, `8000`, `8080`, `8088`, `8501`, `9000`, `9001`

---

## Project structure

```
davao-jeepney-optimization/
├── docker-compose.yml
├── .env
├── Dockerfile                    # Shared image: FastAPI + Streamlit + pipeline
├── Dockerfile.airflow            # Airflow image: base + requirements + dbt deps
├── requirements-airflow.txt      # Python deps baked into Dockerfile.airflow
├── config/
│   ├── setup_conn.py             # Airflow connection bootstrap (runs on api-server start)
│   └── pgadmin/                  # pgAdmin server pre-config
├── init-scripts/                 # PostgreSQL schema init (auto-run on first start)
│   ├── 00_init_databases.sql     # Creates airflow_db
│   ├── 01_roles.sql              # jeepney_admin / jeepney_writer / jeepney_reader
│   ├── 02_users.sql              # svc_pipeline / svc_fastapi / svc_bi
│   ├── 03_database.sql           # Governance comment on jeepney_dw
│   ├── 04_schemas.sql            # staging + marts schemas, grants, default privileges
│   ├── 05_tables_staging.sql     # Silver layer tables (7 entities)
│   ├── 06_tables_marts.sql       # Gold layer tables (4 marts)
│   └── 07_indexes_grants_audit.sql
├── fastapi_app/                  # Bronze ingestion API (7 endpoints, Pydantic v2)
├── producers/                    # Synthetic data generators (8 scripts)
├── ingestion/                    # MinIO Parquet → PostgreSQL loader
├── dbt/                          # Transformations: staging → intermediate → marts
├── science/                      # Clustering + A/B testing + Parquet export
├── streamlit_app/                # Data science app (3 pages)
├── dags/                         # 5 Airflow DAGs (daily at 06:00 PHT)
├── superset/dashboards/          # 3 pre-built Superset dashboard exports
└── pipeline/                     # Dockerfile for one-off pipeline runs
```

![alt text](assets/sketch.png)

---

## Database roles

This project follows the principle of least privilege. Three application users are created by `init-scripts/02_users.sql`:

| User           | Role             | Access                            | Used by                              |
| -------------- | ---------------- | --------------------------------- | ------------------------------------ |
| `svc_pipeline` | `jeepney_admin`  | Full DDL + DML on staging + marts | Airflow DAGs, dbt, ingestion scripts |
| `svc_fastapi`  | `jeepney_writer` | INSERT only on staging schema     | FastAPI ingestion API                |
| `svc_bi`       | `jeepney_reader` | SELECT only on marts schema       | Superset, Streamlit                  |

The `jeepney_user_admin` superuser (set via `POSTGRES_USER` in `.env`) is used **only** by Docker to bootstrap the databases on first start. Application services never connect as superuser.

---

## Quick start

```bash
# 1. Clone and enter the project
git clone https://github.com/ikidevz/davao-jeepney-optimization.git
cd davao-jeepney-optimization

# 2. Set the Airflow UID (Linux only — skip on Mac/Windows)
echo "AIRFLOW_UID=$(id -u)" >> .env

# 3. Start all services
docker-compose up -d

# 4. Wait ~90 seconds for health checks to pass, then verify
docker-compose ps
```

All services should show `healthy` or `running`. PostgreSQL init scripts run automatically on first start — no manual SQL needed.

---

## Service URLs and credentials

| Service           | URL                        | Username             | Password                          |
| ----------------- | -------------------------- | -------------------- | --------------------------------- |
| FastAPI (Swagger) | http://localhost:8000/docs | —                    | —                                 |
| Airflow           | http://localhost:8080      | `airflow_route_user` | `airflow_route_password`          |
| Superset          | http://localhost:8088      | `admin`              | _(set on first init — see below)_ |
| Streamlit         | http://localhost:8501      | —                    | —                                 |
| MinIO Console     | http://localhost:9001      | `jeepney_minio_user` | `jeepney_minio_password`          |
| pgAdmin           | http://localhost:5050      | `admin@example.com`  | `pgadmin_pwd`                     |

> All credentials are defined in `.env` and can be changed before first start.

---

## First-time Superset setup

Run once after `docker-compose up -d`:

```bash
docker exec jeepney_superset superset db upgrade
docker exec jeepney_superset superset init
docker exec jeepney_superset superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname User \
  --email admin@example.com \
  --password admin
```

Then in the Superset UI (http://localhost:8088):

1. Go to **Settings → Database Connections → + Database**
2. Choose **PostgreSQL** and enter:
   ```
   postgresql+psycopg2://svc_bi:bi_pass_123@postgres:5432/jeepney_dw
   ```
   > Superset connects as `svc_bi` (read-only on marts) — never as superuser.
3. Import dashboards from `superset/dashboards/` via **Dashboards → Import**:
   - `route_performance.json` — Route KPIs and delay heatmaps
   - `district_ridership.json` — District boardings and wait times
   - `ab_test_summary.json` — A/B experiment statistical results

> Import `ab_test_summary.json` only after the full pipeline has run — statistical columns (`p_value`, `effect_size`, `confidence_interval_*`) are `NULL` until `dag_04_science` completes.

---

## Run the pipeline

Once all services are healthy, trigger the pipeline through Airflow (http://localhost:8080):

1. Log in with `airflow_route_user` / `airflow_route_password`
2. Enable and manually trigger **dag_01_producers**

The remaining DAGs chain automatically via `TriggerDagRunOperator`:

```
dag_01_producers      → generates synthetic data, POSTs to FastAPI, Parquet lands in MinIO
  └── dag_02_ingestion      → moves Parquet from MinIO into PostgreSQL staging tables
        └── dag_03_dbt_transform  → runs staging + intermediate dbt models
              └── dag_04_science        → clustering, A/B testing, exports Parquet
                    └── dag_05_marts_refresh  → builds final Gold mart tables
```

After `dag_05_marts_refresh` completes, Superset and Streamlit will have live data.

Full pipeline runtime: approximately **30–50 minutes** on first run (~1.1M trip records across 40 routes).

---

## Run pipeline scripts manually

For one-off runs outside Airflow:

```bash
# Run all producers (generates synthetic data and POSTs to FastAPI)
docker-compose run --rm pipeline python /app/producers/produce_all.py

# Run ingestion only (MinIO → PostgreSQL staging)
docker-compose run --rm pipeline python /app/ingestion/ingest_to_postgres.py

# Run dbt staging + intermediate models
docker-compose run --rm pipeline bash -c "cd /app/dbt && dbt run --select staging intermediate"

# Run science pipeline (clustering + A/B testing + Parquet export)
docker-compose run --rm pipeline python /app/science/clustering.py
docker-compose run --rm pipeline python /app/science/ab_testing.py
docker-compose run --rm pipeline python /app/science/export_to_parquet.py

# Run dbt marts (after science scripts complete)
docker-compose run --rm pipeline bash -c "cd /app/dbt && dbt run --select marts"
```

> The `pipeline` service uses `svc_pipeline` (jeepney_admin role) — it has full DDL + DML access needed by dbt.

---

## Data overview

| Entity                 | Volume                       |
| ---------------------- | ---------------------------- |
| Jeepney routes         | 40 (real Davao routes)       |
| Stops                  | ~303 (real Davao landmarks)  |
| Districts              | 11 administrative districts  |
| Barangays              | 182                          |
| Trip records           | ~1,100,000 (365 days)        |
| Passenger surveys      | 5,000                        |
| A/B experiment records | ~8,000 (8 weeks × Cluster 3) |

---

## Commuter clusters

| Cluster | Label              | Characteristics                                        |
| ------- | ------------------ | ------------------------------------------------------ |
| 0       | Student Commuters  | High frequency, low fare, school destinations          |
| 1       | Market Workers     | AM peak, Toril/Calinan → Bankerohan                    |
| 2       | CBD Workers        | Daily, higher willingness to pay, Poblacion/Lanang     |
| 3       | Underserved Riders | 2+ transfers, long wait, low satisfaction — A/B target |
| 4       | Occasional Riders  | Low frequency, mall/hospital trips                     |

---

## A/B experiment

**Hypothesis:** A direct Matina → SM Lanang express route reduces travel time and improves satisfaction for Underserved Riders (Cluster 3).

| Group         | Route             | Avg travel time | Transfers |
| ------------- | ----------------- | --------------- | --------- |
| Control (A)   | Current multi-hop | ~55 min         | 2         |
| Treatment (B) | Direct express    | ~35 min         | 0         |

Statistical tests: two-sample t-test (satisfaction score, travel time) + chi-square (would_use_again) at α = 0.05. Results are written to `marts.mart_ab_test_results` and visualized in Superset Dashboard 3 and the Streamlit A/B test page.

---

## dbt layer summary

| Layer    | Schema         | Models                                                                                                            | Built by |
| -------- | -------------- | ----------------------------------------------------------------------------------------------------------------- | -------- |
| Silver   | `staging`      | 7 tables (stg_routes, stg_stops, stg_vehicles, stg_operators, stg_trips, stg_passenger_survey, stg_ab_experiment) | dag_03   |
| Pre-Gold | `intermediate` | int_daily_ridership, int_route_performance, int_passenger_features                                                | dag_03   |
| Gold     | `marts`        | mart_route_summary, mart_district_ridership, mart_commuter_clusters, mart_ab_test_results                         | dag_05   |

> `mart_commuter_clusters` and `mart_ab_test_results` are empty shells until `dag_04_science` writes cluster labels and p-values back to the staging tables. dbt in `dag_05` then reads those columns to build the final Gold marts.

---

## Airflow connections

Registered automatically by `config/setup_conn.py` on `airflow-apiserver` startup:

| Connection ID      | Type                | Used for                                  |
| ------------------ | ------------------- | ----------------------------------------- |
| `jeepney_postgres` | postgres            | All DAG validation tasks and dbt runs     |
| `jeepney_minio`    | aws (S3-compatible) | MinIO Bronze layer reads and verification |

---

## Stop and clean up

```bash
# Stop all services, keep data volumes
docker-compose down

# Stop all services and delete all data (full reset)
docker-compose down -v
```

The `-v` flag removes named volumes: `postgres-db-volume`, `minio_data`, `superset_home`. Omit it to keep data between restarts.

---

## Troubleshooting

**Airflow workers not starting** — check that `AIRFLOW_UID` is set correctly on Linux:

```bash
echo "AIRFLOW_UID=$(id -u)" >> .env
docker-compose down && docker-compose up -d
```

**PostgreSQL init scripts failed** — the `init-scripts/` folder only runs on a fresh volume. If you've already started once with errors, reset:

```bash
docker-compose down -v && docker-compose up -d
```

**MinIO bucket not created** — check `jeepney_minio_init` container logs:

```bash
docker logs jeepney_minio_init
```

**dbt models failing** — verify `svc_pipeline` was created and granted correctly:

```bash
docker exec -it jeepney_postgres psql -U jeepney_user_admin -d jeepney_dw \
  -c "\du svc_pipeline"
```

**Superset can't connect to PostgreSQL** — confirm the connection uses `svc_bi` (not superuser) and the host is `postgres` (Docker service name), not `localhost`.
