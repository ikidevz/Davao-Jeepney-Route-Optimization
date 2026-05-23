# Davao Jeepney Route Optimization

A full data engineering and data science project analyzing commuter patterns across Davao City's jeepney routes — built on a lightweight data lakehouse with Docker and Python.

---

![alt text](assets/image.png)

## What this project does

- **Ingests** 1,100,000+ synthetic jeepney trip records and 5,000 passenger surveys through a FastAPI Bronze layer into MinIO (Parquet)
- **Transforms** raw data through a three-layer dbt pipeline (staging → intermediate → marts) in PostgreSQL
- **Clusters** commuters into 5 segments using K-Means with Elbow + Silhouette diagnostics and a stable semantic remapping step (Student, Market Worker, CBD Worker, Underserved, Occasional)
- **Runs an A/B experiment** simulating a direct Matina → SM Lanang express route for the worst-served cluster, validated with Welch's t-test, chi-square, Cohen's d, and 95% confidence intervals
- **Surfaces insights** through Apache Superset dashboards and a 4-page Streamlit data science app

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
| DS app                    | Streamlit (4 pages)                    |
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
│   ├── feature_engineering.py    # StandardScaler + feature matrix
│   ├── clustering.py             # K-Means K=5, Elbow/Silhouette sweep, DBSCAN validation
│   ├── ab_testing.py             # Welch's t-test, chi-square, Cohen's d, 95% CI
│   ├── export_to_parquet.py      # Exports mart tables + manifest.json
│   ├── parquet/                  # DuckDB-queryable Parquet outputs
│   └── models/                   # scaler.joblib (persisted StandardScaler)
├── streamlit_app/                # Data science app (4 pages)
│   ├── app.py                    # Landing page: KPIs, route chart, pipeline status
│   └── pages/
│       ├── 01_cluster_explorer.py  # K-Means segments: radar, heatmap, scatter, profiles
│       ├── 02_ab_test_results.py   # A/B stats: CI bands, effect size, lift, verdict
│       ├── 03_route_map.py         # Folium route map: stops, corridors, district overlays
│       └── 04_route_trends.py      # Ridership + revenue trends, DOW heatmap (new)
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
        └── dag_03_dbt_transform  → runs staging + intermediate dbt models + dbt test
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

# Run science pipeline (in order)
docker-compose run --rm pipeline python /app/science/feature_engineering.py
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

## Commuter clustering (K-Means)

The clustering pipeline in `science/clustering.py` segments 5,000 passenger survey records into 5 behavioral groups. Here is exactly what it does and why.

### Feature matrix

Seven features are pulled from `intermediate.int_passenger_features` after dbt has run, then standardized with `StandardScaler` (zero mean, unit variance) before any model runs. Standardization prevents high-magnitude features like `travel_time_min` from dominating features that live on a 1–5 scale.

| Feature                  | What it captures                                            |
| ------------------------ | ----------------------------------------------------------- |
| `trips_per_week`         | Commute frequency — separates daily from occasional riders  |
| `avg_fare_paid_php`      | Willingness to pay — proxy for income bracket and route use |
| `transfers_required`     | Route complexity — key discriminator for underserved riders |
| `wait_time_min`          | Service quality — long waits signal supply gaps             |
| `travel_time_min`        | Total journey time — captures distance and route efficiency |
| `satisfaction_score`     | Revealed preference — 1–5 self-reported satisfaction        |
| `income_bracket_encoded` | Ordinal income (low=0, mid=1, high=2) — socioeconomic lens  |

The fitted scaler is persisted to `science/models/scaler.joblib` so it can be reused for inference without refitting.

### Choosing K

K is not hardcoded arbitrarily. The pipeline sweeps **K = 2 through 10** and computes two diagnostics:

**Elbow method (Within-Cluster Sum of Squares):** WSS is recorded for each K with `n_init=10`. The elbow — where marginal gain from adding another cluster diminishes sharply — is a heuristic indicator of a good K. Results are saved to `science/parquet/elbow_scores.parquet`.

**Silhouette score:** For each K the mean silhouette coefficient is computed over a 2,000-sample draw. A silhouette coefficient near +1 means a point is well-matched to its own cluster and poorly matched to neighbours; near 0 means borderline; below 0 suggests misclassification. The K with the highest mean silhouette is auto-selected as the algorithmic recommendation. Results are saved to `science/parquet/silhouette_scores.parquet`.

Both diagnostics are plotted in the Streamlit Cluster Explorer under **Model Diagnostics**. For this dataset both methods converge on **K = 5**, which matches the five commuter archetypes engineered into the synthetic data.

### Stable semantic labels (remapping step)

K-Means assigns cluster IDs (0–4) non-deterministically. Running the model twice with different seeds can swap which raw ID corresponds to which archetype — breaking any downstream code that hardcodes "Cluster 3 = Underserved Riders."

After the initial fit, a **greedy prototype-scoring remapper** assigns stable semantic IDs. Each raw cluster is scored against five prototype profiles based on its centroid position in the feature space, then assigned to semantic IDs in priority order (Underserved → CBD → Student → Occasional → Market). Labels stay consistent across pipeline runs regardless of random seed.

### DBSCAN validation

After K-Means finalizes, DBSCAN runs with `eps=1.2` and `min_samples=15` on the same scaled matrix as a sanity check — not for final labels. If DBSCAN finds more than ~5% noise points (label = −1), it signals that the feature space has significant outlier structure that K-Means is absorbing rather than isolating. For this dataset, noise is consistently below 3%, confirming the K-Means partitions are structurally sound.

### The five clusters

| Cluster | Label                  | Characteristics                                                                                                                  |
| ------- | ---------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 0       | **Student Commuters**  | High frequency (10+ trips/week), low fare (~₱14.50), school destinations, Talomo/Buhangin/Agdao origin districts                 |
| 1       | **Market Workers**     | AM peak heavy, Toril/Calinan/Tugbok → Bankerohan corridor, low income bracket                                                    |
| 2       | **CBD Workers**        | Daily commuters, higher willingness to pay (~₱19), Poblacion/Lanang destinations, prefer aircon                                  |
| 3       | **Underserved Riders** | 2+ transfers required, 30-min average wait, 55-min average travel time, satisfaction score 1–2, low income — **A/B test target** |
| 4       | **Occasional Riders**  | 1–2 trips/week, mall/hospital trips, mixed income, Talomo/Buhangin/Toril/Agdao spread                                            |

Cluster labels are written back to `stg_passenger_survey` via batched `UPDATE` (500-row pages using `psycopg2.extras.execute_batch`), then surfaced in `mart_commuter_clusters` for Superset and Streamlit to slice by segment.

---

## A/B experiment

The A/B experiment in `science/ab_testing.py` tests a single hypothesis against Cluster 3 passengers using three statistical methods.

### Hypothesis and design

**Hypothesis:** A direct Matina → SM Lanang express route (Route R12) — zero transfers, ~35 minutes — produces a statistically significant improvement in satisfaction and a measurable reduction in travel time for Underserved Riders (Cluster 3).

| Parameter        | Value                                                     |
| ---------------- | --------------------------------------------------------- |
| Population       | 1,000 Cluster 3 passengers from `stg_passenger_survey`    |
| Assignment       | 50/50 random split — 500 control, 500 treatment           |
| Duration         | 8 simulated weeks, one observation per passenger per week |
| Primary metric   | `satisfaction_score` (1–5) — Welch's two-sample t-test    |
| Secondary metric | `would_use_again` (boolean) — chi-square test             |
| Tertiary metric  | `simulated_travel_time_min` — Welch's two-sample t-test   |
| α level          | 0.05, target power 0.80                                   |

If either group falls outside 40–60% of total enrollment, the pipeline logs a warning before running any tests.

### What each group experiences

| Group         | Route              | Avg travel time | Transfers | Avg satisfaction               |
| ------------- | ------------------ | --------------- | --------- | ------------------------------ |
| Control (A)   | Existing multi-hop | ~55 min         | 1–2       | ~2.2 (week 1) → declining      |
| Treatment (B) | Direct express     | ~35 min         | 0         | ~3.8 (week 1) → rising to ~4.4 |

### Statistical methods

**Welch's two-sample t-test** — used for `satisfaction_score` and `simulated_travel_time_min`. Unlike the standard Student's t-test, Welch's variant does not assume equal variance between groups, making it more robust when control and treatment scores have different spreads — the typical case in real-world survey data. Implemented via `scipy.stats.ttest_ind(equal_var=False)`. Output: t-statistic, two-tailed p-value, significance flag (`p_value < 0.05`).

**Chi-square test of independence** — used for `would_use_again` (yes/no). Tests whether the distribution of yes/no responses is independent of group assignment. Computes a 2×2 contingency table, chi-square statistic, degrees of freedom, and p-value. Control passengers answer "yes" at ~45%; treatment passengers at ~82% — a 37-point lift that produces a strongly significant result.

**Cohen's d (effect size)** — computed alongside each t-test as `(treatment_mean − control_mean) / pooled_std`. Statistical significance alone does not confirm practical importance; a dataset large enough will make any difference significant. Cohen's d quantifies the magnitude:

| Range             | Interpretation |
| ----------------- | -------------- |
| \|d\| < 0.2       | Negligible     |
| 0.2 ≤ \|d\| < 0.5 | Small          |
| 0.5 ≤ \|d\| < 0.8 | Medium         |
| \|d\| ≥ 0.8       | Large          |

A medium-to-large Cohen's d alongside p < 0.05 is the combination that justifies a route adoption recommendation.

**95% confidence intervals** — computed for each continuous metric as `mean_diff ± 1.96 × SE`, where `SE = sqrt(var_ctrl/n_ctrl + var_trt/n_trt)`. A CI that excludes zero confirms significance at α = 0.05. Both bounds are persisted and displayed on the Streamlit CI chart.

### Possible outcomes and what each means

The experiment can resolve in four ways:

**Significant improvement, medium-to-large effect** — p < 0.05 and Cohen's d ≥ 0.5. The recommendation is clear: adopt the route. Next step is a real-world pilot with load-factor monitoring and a 6-month ridership review.

**Significant but small effect** — p < 0.05 but Cohen's d below 0.3. The improvement is real but may not justify operating cost. Extend the trial, run qualitative interviews to understand why satisfaction lift is muted, and model cost-per-satisfaction-point against alternative interventions (frequency increase, feeder route redesign).

**Not significant, trend visible** — p > 0.05 but weekly satisfaction in the treatment group is rising. The experiment may be underpowered. Extend to 12–16 weeks, increase sample size, and retest. Do not adopt the route based on a trend alone.

**No improvement** — p > 0.05, Cohen's d near zero, no visible trend. This is a genuine null result. Investigate why: access issues at the Matina origin stop, affordability barriers to the express fare, or a mismatch between the route corridor and Cluster 3's actual destination patterns. A different intervention is needed.

### Where results live

All statistical outputs are written to two locations:

- `marts.mart_ab_test_results` — weekly metrics + test results, read by Superset Dashboard 3 (`ab_test_summary.json`)
- `science/parquet/ab_test_statistics.parquet` — DuckDB-queryable, read by the Streamlit A/B page

Columns include: `p_value`, `is_significant`, `t_statistic`, `effect_size`, `mean_diff`, `ci_low_95`, `ci_high_95`, `control_mean`, `treatment_mean`.

The Streamlit A/B page renders: weekly trend with shaded 95% CI bands, statistical results table, confidence interval forest plot, travel time box plot, fare distribution violin chart, satisfaction lift by origin, and a plain-language verdict.

---

## dbt layer summary

| Layer    | Schema         | Models                                                                                                            | Built by |
| -------- | -------------- | ----------------------------------------------------------------------------------------------------------------- | -------- |
| Silver   | `staging`      | 7 tables (stg_routes, stg_stops, stg_vehicles, stg_operators, stg_trips, stg_passenger_survey, stg_ab_experiment) | dag_03   |
| Pre-Gold | `intermediate` | int_daily_ridership, int_route_performance, int_passenger_features                                                | dag_03   |
| Gold     | `marts`        | mart_route_summary, mart_district_ridership, mart_commuter_clusters, mart_ab_test_results                         | dag_05   |

> `mart_commuter_clusters` and `mart_ab_test_results` are empty shells until `dag_04_science` writes cluster labels and p-values back to the staging tables. dbt in `dag_05` then reads those enriched columns to build the final Gold marts.

Every model has a `schema.yml` with column descriptions and dbt tests (`not_null`, `unique`, `accepted_values`, `relationships`). Data quality is enforced at transformation time, not at query time.

---

## Streamlit app pages

| Page                    | File                     | What it shows                                                                                                     |
| ----------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| Landing                 | `app.py`                 | Live KPIs, route performance chart, district ridership, pipeline status table                                     |
| 🔵 Cluster Explorer     | `01_cluster_explorer.py` | Radar chart, feature heatmap, scatter plot, income/purpose breakdown, profile cards, elbow/silhouette diagnostics |
| 🧪 A/B Test Results     | `02_ab_test_results.py`  | Weekly satisfaction with CI bands, statistical results table, CI forest plot, lift by origin, verdict             |
| 🗺️ Route Map            | `03_route_map.py`        | Folium map with route corridors, stop markers, district satisfaction circles, fullscreen + minimap plugins        |
| 📈 Route Trends _(new)_ | `04_route_trends.py`     | Daily ridership trend, revenue chart, DOW heatmap, district area chart, top/bottom routes                         |

All pages query Parquet via DuckDB — no live PostgreSQL connection required at dashboard runtime.

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

**Streamlit shows no data** — confirm `dag_04_science` has completed and Parquet files exist:

```bash
docker exec jeepney_streamlit ls /app/parquet/
```

Expected files: `passenger_features.parquet`, `cluster_assignments.parquet`, `elbow_scores.parquet`, `silhouette_scores.parquet`, `ab_test_statistics.parquet`, `mart_commuter_clusters.parquet`, `mart_ab_test_results.parquet`, `mart_route_summary_recent.parquet`, `mart_district_ridership_recent.parquet`, `manifest.json`.

**Superset can't connect to PostgreSQL** — confirm the connection uses `svc_bi` (not superuser) and the host is `postgres` (Docker service name), not `localhost`.

**Cluster labels not appearing in Superset** — `dag_04_science` must complete before `dag_05_marts_refresh`. If you triggered mart refresh manually before science finished, re-trigger `dag_05_marts_refresh` after confirming `cluster_id` is populated in `stg_passenger_survey`.
