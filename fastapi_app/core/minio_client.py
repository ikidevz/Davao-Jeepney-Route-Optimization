import io
from datetime import date

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import ClientError
from botocore.config import Config

from core.config import settings


def get_client():
    """Return a boto3 S3 client pointed at MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",  # required by boto3 even for MinIO
    )


def ensure_bucket(client) -> None:
    """Create the raw bucket if it does not exist."""
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.minio_bucket)


def write_parquet(
    records: list[dict],
    entity: str,
    partition_date: date | None = None,
) -> str:
    """
    Convert a list of dicts to Parquet and upload to MinIO.

    Path convention:
        s3://raw/jeepney/{entity}/date={YYYY-MM-DD}/{entity}.parquet

    Returns the full S3 key of the uploaded file.
    """
    if not records:
        raise ValueError(f"No records to write for entity '{entity}'.")

    run_date = partition_date or date.today()
    s3_key = f"jeepney/{entity}/date={run_date.isoformat()}/{entity}.parquet"

    # Convert to Arrow table then Parquet bytes
    table = pa.Table.from_pylist(records)
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="snappy")
    buffer.seek(0)

    client = get_client()
    ensure_bucket(client)
    client.upload_fileobj(buffer, settings.minio_bucket, s3_key)

    return f"s3://{settings.minio_bucket}/{s3_key}"
