from datetime import date
from fastapi import APIRouter, HTTPException, Query
from core.minio_client import write_parquet
from schemas.trip import TripPayload
from schemas.common import IngestResponse

router = APIRouter(prefix="/ingest", tags=["Trips"])


@router.post(
    "/trips",
    response_model=IngestResponse,
    summary="Ingest daily trip/ridership fact records",
    description=(
        "Accepts a batch of trip records (~500K total over 1 year). "
        "is_on_time and delay_min are cross-validated (on_time = True requires delay <= 5). "
        "load_factor must be between 0.0 and 1.5. "
        "Writes Parquet to s3://raw/jeepney/trips/date={partition_date}/trips.parquet. "
        "For large batches, call this endpoint in chunks of 10,000 records."
    ),
)
def ingest_trips(
    payload: list[TripPayload],
    partition_date: date = Query(default=None),
    chunk_index: int = Query(default=None),
) -> IngestResponse:
    if not payload:
        raise HTTPException(
            status_code=422, detail="Payload must contain at least one record.")

    # Serialize date and time to ISO strings for PyArrow compatibility
    records = []
    for r in payload:
        rec = r.model_dump()
        rec["trip_date"] = rec["trip_date"].isoformat()
        rec["departure_time"] = rec["departure_time"].isoformat()
        rec["arrival_time"] = rec["arrival_time"].isoformat()
        records.append(rec)

    try:
        s3_path = write_parquet(
            records, entity="trips", partition_date=partition_date, chunk_index=chunk_index)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"MinIO write failed: {exc}")

    return IngestResponse(
        status="success",
        entity="trips",
        rows_written=len(records),
        s3_path=s3_path,
        partition_date=str(partition_date or date.today()),
    )
