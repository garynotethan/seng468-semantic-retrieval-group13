import os
from minio import Minio
import urllib3

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
BUCKET_NAME = "documents"

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def init_bucket():
    try:
        if not client.bucket_exists(BUCKET_NAME):
            client.make_bucket(BUCKET_NAME)
    except urllib3.exceptions.MaxRetryError:
        print("Warning: MinIO is not ready yet.")
        raise

def upload_file(file_data, object_name, length):
    client.put_object(
        BUCKET_NAME,
        object_name,
        file_data,
        length,
        content_type="application/pdf"
    )

def delete_file(object_name):
    try:
        client.remove_object(BUCKET_NAME, object_name)
    except Exception:
        pass
