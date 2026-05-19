from __future__ import annotations

import os
import subprocess


def add_connection(conn_id: str, command: list[str]) -> None:
    """Add an Airflow connection, replacing it if it already exists."""
    try:
        print(f"  Adding connection '{conn_id}'...")
        result = subprocess.run(command, check=True,
                                capture_output=True, text=True)
        print(f"  '{conn_id}' added successfully.")
        if result.stdout.strip():
            print(f"  {result.stdout.strip()}")

    except subprocess.CalledProcessError as e:
        if "already exists" in (e.stderr or ""):
            print(f"  '{conn_id}' already exists — deleting and recreating...")
            subprocess.run(
                ["airflow", "connections", "delete", conn_id],
                check=True,
                capture_output=True,
            )
            subprocess.run(command, check=True)
            print(f"  '{conn_id}' updated successfully.")
        else:
            print(f"  ERROR adding '{conn_id}': {e.stderr}")
            raise


if __name__ == "__main__":
    print("=" * 55)
    print("  AIRFLOW CONNECTION SETUP — Davao Jeepney Pipeline")
    print("=" * 55)

    print("\n[1/2] PostgreSQL (jeepney_dw)")
    add_connection(
        conn_id="jeepney_postgres",
        command=[
            "airflow", "connections", "add", "jeepney_postgres",
            "--conn-type",     "postgres",
            "--conn-host",     os.getenv("POSTGRES_HOST",         "postgres"),
            "--conn-port",     os.getenv("POSTGRES_PORT",         "5432"),
            "--conn-schema",   os.getenv("POSTGRES_DB",
                                         "jeepney_dw"),
            "--conn-login",    os.getenv("SVC_PIPELINE_USER",
                                         "svc_pipeline"),
            "--conn-password", os.getenv("SVC_PIPELINE_PASSWORD", ""),
        ],
    )

    print("\n[2/2] MinIO (S3-compatible Bronze store)")
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    add_connection(
        conn_id="jeepney_minio",
        command=[
            "airflow", "connections", "add", "jeepney_minio",
            "--conn-type",     "aws",
            "--conn-login",    os.getenv("MINIO_ACCESS_KEY", ""),
            "--conn-password", os.getenv("MINIO_SECRET_KEY", ""),
            "--conn-extra",    f'{{"endpoint_url": "http://{minio_endpoint}"}}',
        ],
    )

    print("\n" + "=" * 55)
    print("  All connections registered. Starting Airflow api-server.")
    print("=" * 55 + "\n")
