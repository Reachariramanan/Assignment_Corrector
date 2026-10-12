import os
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://localhost:19100")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "dsa_admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "dsa_local_dev_password")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "dsa-submissions")


@lru_cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket() -> None:
    client = _client()
    existing = [b["Name"] for b in client.list_buckets().get("Buckets", [])]
    if MINIO_BUCKET not in existing:
        client.create_bucket(Bucket=MINIO_BUCKET)


def put_file(key: str, path: Path) -> str:
    ensure_bucket()
    _client().upload_file(str(path), MINIO_BUCKET, key)
    return key


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    ensure_bucket()
    _client().put_object(Bucket=MINIO_BUCKET, Key=key, Body=data, ContentType=content_type)
    return key


def get_bytes(key: str) -> bytes:
    resp = _client().get_object(Bucket=MINIO_BUCKET, Key=key)
    return resp["Body"].read()


def presigned_url(key: str, expires_in: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object", Params={"Bucket": MINIO_BUCKET, "Key": key}, ExpiresIn=expires_in
    )
