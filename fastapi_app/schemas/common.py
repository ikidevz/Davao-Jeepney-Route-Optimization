from pydantic import BaseModel


class IngestResponse(BaseModel):
    """
    Standard response returned by every POST /ingest/* endpoint.
    Confirms how many rows were written and where they landed in MinIO.
    """
    status: str           # "success" or "error"
    entity: str           # e.g. "routes", "trips", "passengers"
    rows_written: int     # number of records written to Parquet
    s3_path: str          # full MinIO path: s3://raw/jeepney/{entity}/date=.../
    partition_date: str   # ISO date string: YYYY-MM-DD
