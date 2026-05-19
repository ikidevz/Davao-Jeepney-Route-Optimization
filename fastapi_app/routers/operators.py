from datetime import date
from fastapi import APIRouter, HTTPException, Query
from core.minio_client import write_parquet
from schemas.operator import OperatorPayload
from schemas.common import IngestResponse

router = APIRouter(prefix="/ingest", tags=["Operators"])


@router.post(
    "/operators",
    response_model=IngestResponse,
    summary="Ingest jeepney operator/franchise holder records",
    description=(
        "Accepts a batch of operator records. franchise_type must be one of: "
        "individual | cooperative | corporation. "
        "Writes Parquet to s3://raw/jeepney/operators/date={partition_date}/operators.parquet"
    ),
)
def ingest_operators(
    payload: list[OperatorPayload],
    partition_date: date = Query(default=None),
) -> IngestResponse:
    if not payload:
        raise HTTPException(status_code=422, detail="Payload must contain at least one record.")

    records = [r.model_dump() for r in payload]

    try:
        s3_path = write_parquet(records, entity="operators", partition_date=partition_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"MinIO write failed: {exc}")

    return IngestResponse(
        status="success",
        entity="operators",
        rows_written=len(records),
        s3_path=s3_path,
        partition_date=str(partition_date or date.today()),
    )
