from datetime import date
from fastapi import APIRouter, HTTPException, Query
from core.minio_client import write_parquet
from schemas.vehicle import VehiclePayload
from schemas.common import IngestResponse

router = APIRouter(prefix="/ingest", tags=["Vehicles"])


@router.post(
    "/vehicles",
    response_model=IngestResponse,
    summary="Ingest jeepney vehicle/fleet records",
    description=(
        "Accepts a batch of vehicle records. vehicle_type must be traditional or "
        "modernized_PUV. fuel_type must be diesel | euro4_diesel | electric. "
        "Writes Parquet to s3://raw/jeepney/vehicles/date={partition_date}/vehicles.parquet"
    ),
)
def ingest_vehicles(
    payload: list[VehiclePayload],
    partition_date: date = Query(default=None),
) -> IngestResponse:
    if not payload:
        raise HTTPException(status_code=422, detail="Payload must contain at least one record.")

    records = [r.model_dump() for r in payload]

    try:
        s3_path = write_parquet(records, entity="vehicles", partition_date=partition_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MinIO write failed: {exc}")

    return IngestResponse(
        status="success",
        entity="vehicles",
        rows_written=len(records),
        s3_path=s3_path,
        partition_date=str(partition_date or date.today()),
    )
