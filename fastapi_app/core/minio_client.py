import io
from datetime import date

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.exceptions import ClientError
from botocore.config import Config

from core.config import settings


def get_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket(client) -> None:
    bucket = settings.minio_bucket
    try:
        client.head_bucket(Bucket=bucket)
        print(f"✅ Bucket '{bucket}' exists")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            print(f"Creating bucket '{bucket}'...")
            client.create_bucket(Bucket=bucket)
        else:
            raise


def write_parquet(
    records: list[dict],
    entity: str,
    partition_date: date | None = None,
    chunk_index: int | None = None,
) -> str:
    if not records:
        raise ValueError(f"No records to write for entity '{entity}'.")

    run_date = partition_date or date.today()
    suffix = f"_{chunk_index:05d}" if chunk_index is not None else ""
    s3_key = f"jeepney/{entity}/date={run_date.isoformat()}/{entity}{suffix}.parquet"

    try:
        table = pa.Table.from_pylist(records)
        buffer = io.BytesIO()
        pq.write_table(table, buffer, compression="snappy")
        buffer.seek(0)

        client = get_client()
        ensure_bucket(client)

        client.upload_fileobj(buffer, settings.minio_bucket, s3_key)

        full_path = f"s3://{settings.minio_bucket}/{s3_key}"
        print(f"✅ Successfully wrote {len(records)} records to {full_path}")
        return full_path

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        raise RuntimeError(
            f"MinIO ClientError [{error_code}]: {error_msg}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to write parquet: {e}") from e
