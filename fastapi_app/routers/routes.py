from datetime import date
from fastapi import APIRouter, HTTPException, Query
from core.minio_client import write_parquet
from schemas.route import RoutePayload
from schemas.common import IngestResponse

router = APIRouter(prefix="/ingest", tags=["Routes"])


@router.post(
    "/routes",
    response_model=IngestResponse,
    summary="Ingest jeepney route dimension records",
    description=(
        "Accepts a batch of route records validated by Pydantic v2. "
        "Converts to Parquet and writes to MinIO Bronze layer at "
        "s3://raw/jeepney/routes/date={partition_date}/routes.parquet"
    ),
)
def ingest_routes(
    payload: list[RoutePayload],
    partition_date: date = Query(default=None, description="Override partition date (YYYY-MM-DD). Defaults to today."),
) -> IngestResponse:
    if not payload:
        raise HTTPException(status_code=422, detail="Payload must contain at least one record.")

    records = [r.model_dump() for r in payload]

    try:
        s3_path = write_parquet(records, entity="routes", partition_date=partition_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MinIO write failed: {exc}")

    return IngestResponse(
        status="success",
        entity="routes",
        rows_written=len(records),
        s3_path=s3_path,
        partition_date=str(partition_date or date.today()),
    )
