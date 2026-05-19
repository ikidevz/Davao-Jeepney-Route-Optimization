from datetime import date
from fastapi import APIRouter, HTTPException, Query
from core.minio_client import write_parquet
from schemas.ab_experiment import ABExperimentPayload
from schemas.common import IngestResponse

router = APIRouter(prefix="/ingest", tags=["A/B Experiment"])


@router.post(
    "/ab-experiment",
    response_model=IngestResponse,
    summary="Ingest A/B experiment records for Cluster 3 (Underserved Riders)",
    description=(
        "Accepts A/B experiment records. Only Cluster 3 passengers are allowed "
        "(cluster_id must be 3). group and route_variant are cross-validated: "
        "control → A_existing_route, treatment → B_express_direct. "
        "Statistical outputs (p_value, effect_size, CI) are NOT part of this payload — "
        "they are computed by science/ab_testing.py and written to marts.mart_ab_test_results. "
        "Writes Parquet to s3://raw/jeepney/ab_experiment/date={partition_date}/ab_experiment.parquet"
    ),
)
def ingest_ab_experiment(
    payload: list[ABExperimentPayload],
    partition_date: date = Query(default=None),
) -> IngestResponse:
    if not payload:
        raise HTTPException(status_code=422, detail="Payload must contain at least one record.")

    records = [r.model_dump() for r in payload]

    try:
        s3_path = write_parquet(records, entity="ab_experiment", partition_date=partition_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MinIO write failed: {exc}")

    return IngestResponse(
        status="success",
        entity="ab_experiment",
        rows_written=len(records),
        s3_path=s3_path,
        partition_date=str(partition_date or date.today()),
    )
