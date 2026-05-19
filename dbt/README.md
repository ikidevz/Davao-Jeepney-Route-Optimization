# dbt — Davao Jeepney Route Optimization

Transformation layer of the **Davao City Jeepney Route Optimization** data lakehouse.

Converts cleaned Silver data (PostgreSQL `staging` schema) into Gold analytics tables (`marts` schema) consumed by Apache Superset dashboards and a Streamlit data science app.

---

## Project Structure

```
jeepney_dw/
├── dbt_project.yml              # Project config, materialization defaults per layer
├── profiles.yml                 # Connection profiles (dev / ci / prod)
├── packages.yml                 # dbt_utils dependency
│
├── models/
│   ├── staging/                 # Silver → views (7 models)
│   │   ├── schema.yml           # Sources, column docs, and tests
│   │   ├── stg_routes.sql
│   │   ├── stg_operators.sql
│   │   ├── stg_stops.sql
│   │   ├── stg_vehicles.sql
│   │   ├── stg_trips.sql
│   │   ├── stg_passenger_survey.sql
│   │   └── stg_ab_experiment.sql
│   │
│   ├── intermediate/            # Business logic → ephemeral/table (3 models)
│   │   ├── schema.yml
│   │   ├── int_daily_ridership.sql
│   │   ├── int_route_performance.sql
│   │   └── int_passenger_features.sql   ← materialised as TABLE for science/ scripts
│   │
│   └── marts/                   # Gold → tables (4 models)
│       ├── schema.yml
│       ├── mart_route_summary.sql
│       ├── mart_district_ridership.sql
│       ├── mart_commuter_clusters.sql   ← empty until clustering.py runs
│       └── mart_ab_test_results.sql     ← stats NULL until ab_testing.py runs
│
├── macros/
│   ├── generate_schema_name.sql         # Prevents "staging_staging" naming bug
│   ├── get_current_ph_timestamp.sql     # PHT audit timestamps
│   ├── encode_income_bracket.sql        # Reusable ordinal encoding
│   └── assert_column_is_positive.sql    # Generic test macro
│
├── tests/
│   ├── staging/
│   │   ├── test_stg_trips_on_time_consistency.sql
│   │   ├── test_stg_trips_load_factor_range.sql
│   │   ├── test_stg_ab_experiment_group_variant_alignment.sql
│   │   └── test_stg_ab_experiment_only_cluster_3.sql
│   └── marts/
│       ├── test_mart_route_summary_on_time_count_lte_total.sql
│       ├── test_mart_commuter_clusters_ab_eligibility.sql
│       ├── test_mart_district_ridership_peak_lte_total.sql
│       └── test_mart_ab_test_results_ci_order.sql
│
└── analyses/
    ├── route_efficiency_analysis.sql    # Annual route KPI leaderboard
    └── cluster_profile_summary.sql      # Cluster feature averages for Streamlit
```

---

## Model DAG

```
[staging — 7 views]
stg_routes  stg_operators  stg_stops  stg_vehicles  stg_trips  stg_passenger_survey  stg_ab_experiment
      │                                     │                         │                       │
      └─────────────┬───────────────────────┘                         │                       │
                    │                                                  │                       │
         [intermediate — 3 models]                                     │                       │
         int_daily_ridership          ←── stg_trips + stg_routes       │                       │
         int_route_performance        ←── stg_trips + stg_routes + stg_vehicles + stg_operators│
         int_passenger_features (TABLE) ← stg_passenger_survey + stg_routes  ←────────────────┘
                    │                        ↑
                    │           science/clustering.py reads this
                    │
         [marts — 4 tables]
         mart_route_summary        ←── int_route_performance
         mart_district_ridership   ←── int_daily_ridership + stg_stops + stg_passenger_survey
         mart_commuter_clusters    ←── int_passenger_features  (empty until clustering.py)
         mart_ab_test_results      ←── stg_ab_experiment + mart_commuter_clusters
```

---

## Run Order

### First-time / daily pipeline (Airflow DAG chain):

```bash
# 1. Install packages
dbt deps

# 2. Stage + intermediate only (science/ reads int_passenger_features)
dbt run  --select staging intermediate
dbt test --select staging intermediate

# 3. Run science pipeline (outside dbt)
python science/clustering.py   # writes cluster_id back to stg_passenger_survey
python science/ab_testing.py   # writes p_value etc. to staging / exports Parquet

# 4. Mart models (depend on science output)
dbt run  --select marts
dbt test --select marts
```

### Quick full run (development only — skips science dependency):

```bash
dbt run  # will build mart_commuter_clusters and mart_ab_test_results as empty
dbt test --exclude mart_commuter_clusters mart_ab_test_results
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Staging models are **views** | Zero storage cost; always reflect latest ingest |
| `int_passenger_features` is a **table** | `science/clustering.py` needs to `SELECT` it directly from PostgreSQL |
| Mart models are **full-replace tables** | Superset reads a complete consistent snapshot; avoids incremental complexity |
| `generate_schema_name` macro overridden | Prevents dbt from creating `staging_staging` / `dev_marts` schema names |
| `"group"` always quoted | `GROUP` is a PostgreSQL reserved word — enforced in all SQL files |
| `mart_commuter_clusters` guards on `cluster_id IS NOT NULL` | Prevents empty/NULL rows from appearing in Superset before science runs |

---

## Environment Variables

| Variable | Default (Docker dev) | Purpose |
|---|---|---|
| `JEEPNEY_PG_HOST` | `localhost` | PostgreSQL host |
| `JEEPNEY_PG_PASSWORD` | `pipeline_pass` | svc_pipeline password |

Set in production via secrets manager; never commit real passwords.
