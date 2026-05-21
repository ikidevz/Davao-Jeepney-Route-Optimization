from datetime import date
from fastapi import APIRouter, HTTPException, Query
from core.minio_client import write_parquet
from schemas.stop import StopPayload
from schemas.common import IngestResponse

router = APIRouter(prefix="/ingest", tags=["Stops"])


@router.post(
    "/stops",
    response_model=IngestResponse,
    summary="Ingest jeepney stop dimension records",
    description=(
        "Accepts a batch of stop records. Coordinates are validated against "
        "Davao City geographic bounds (lat 6.8–7.5, lon 125.0–126.0). "
        "Writes Parquet to s3://raw/jeepney/stops/date={partition_date}/stops.parquet"
    ),
)
def ingest_stops(
    payload: list[StopPayload],
    partition_date: date = Query(default=None),
    chunk_index: int = Query(default=None),
) -> IngestResponse:
    if not payload:
        raise HTTPException(
            status_code=422, detail="Payload must contain at least one record.")

    records = [r.model_dump() for r in payload]

    try:
        s3_path = write_parquet(
            records, entity="stops", partition_date=partition_date, chunk_index=chunk_index)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"MinIO write failed: {exc}")

    return IngestResponse(
        status="success",
        entity="stops",
        rows_written=len(records),
        s3_path=s3_path,
        partition_date=str(partition_date or date.today()),
    )
