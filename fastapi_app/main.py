from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.config import settings
from routers import routes, stops, operators, vehicles, trips, passengers, ab_experiment

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Davao Jeepney — Bronze Ingestion API",
    description=(
        "FastAPI service that acts as the Bronze layer entry point for the "
        "Davao Jeepney Route Optimization Data Lakehouse. "
        "Data producers POST JSON payloads here. "
        "Each endpoint validates with Pydantic v2, converts to Parquet, "
        "and writes to MinIO at s3://raw/jeepney/{entity}/date=YYYY-MM-DD/. "
        "\n\n**Run order:** routes → operators → stops → vehicles → trips → passengers → ab-experiment"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Routers — one per entity, in FK-safe order
# ---------------------------------------------------------------------------

app.include_router(routes.router)       # no FK dependencies
app.include_router(operators.router)    # no FK dependencies
app.include_router(stops.router)        # FK → routes
app.include_router(vehicles.router)     # FK → routes, operators
app.include_router(trips.router)        # FK → routes, vehicles
app.include_router(passengers.router)   # FK → routes
app.include_router(ab_experiment.router)  # FK → passengers

# ---------------------------------------------------------------------------
# Health + info endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"], summary="API health check")
def health():
    return JSONResponse({
        "status": "ok",
        "service": "jeepney-fastapi",
        "environment": settings.app_env,
        "minio_endpoint": settings.minio_endpoint,
        "minio_bucket": settings.minio_bucket,
    })


@app.get("/", tags=["Health"], summary="Root — API info")
def root():
    return JSONResponse({
        "service": "Davao Jeepney Bronze Ingestion API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "routes":        "POST /ingest/routes",
            "operators":     "POST /ingest/operators",
            "stops":         "POST /ingest/stops",
            "vehicles":      "POST /ingest/vehicles",
            "trips":         "POST /ingest/trips",
            "passengers":    "POST /ingest/passengers",
            "ab_experiment": "POST /ingest/ab-experiment",
        },
        "bronze_path": f"s3://{settings.minio_bucket}/jeepney/{{entity}}/date={{YYYY-MM-DD}}/{{entity}}.parquet",
        "run_order": [
            "routes", "operators", "stops",
            "vehicles", "trips", "passengers", "ab-experiment"
        ],
    })
