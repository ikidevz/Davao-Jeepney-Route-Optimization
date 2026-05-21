from datetime import date
from fastapi import APIRouter, HTTPException, Query
from core.minio_client import write_parquet
from schemas.passenger import PassengerPayload
from schemas.common import IngestResponse

router = APIRouter(prefix="/ingest", tags=["Passengers"])


@router.post(
    "/passengers",
    response_model=IngestResponse,
    summary="Ingest passenger survey records",
    description=(
        "Accepts a batch of 5,000 commuter survey records. "
        "cluster_id and cluster_label are NOT included here — "
        "they are written by science/clustering.py after K-Means runs. "
        "Writes Parquet to s3://raw/jeepney/passengers/date={partition_date}/passengers.parquet"
    ),
)
def ingest_passengers(
    payload: list[PassengerPayload],
    partition_date: date = Query(default=None),
    chunk_index: int = Query(default=None),
) -> IngestResponse:
    if not payload:
        raise HTTPException(
            status_code=422, detail="Payload must contain at least one record.")

    records = []
    for r in payload:
        rec = r.model_dump()
        rec["survey_date"] = rec["survey_date"].isoformat()
        records.append(rec)

    try:
        s3_path = write_parquet(records, entity="passengers",
                                partition_date=partition_date, chunk_index=chunk_index)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"MinIO write failed: {exc}")

    return IngestResponse(
        status="success",
        entity="passengers",
        rows_written=len(records),
        s3_path=s3_path,
        partition_date=str(partition_date or date.today()),
    )
