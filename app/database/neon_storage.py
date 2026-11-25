from core import settings
import boto3

from botocore.config import Config


s3_client = boto3.client(
    "s3",
    endpoint_url=settings.AWS_ENDPOINT_URL_S3,
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    config=Config(
        s3={"addressing_style": "path"}
    )
)


def upload_file(file_object, object_key: str, content_type: str):
    """Upload a file-like object to Neon Object Storage."""

    s3_client.upload_fileobj(
        Fileobj=file_object,
        Bucket=settings.NEON_STORAGE_BUCKET,
        Key=object_key,
        ExtraArgs={
            "ContentType": content_type
        }
    )

    return object_key


def delete_file(object_key: str):
    """Delete an object from Neon Object Storage."""

    s3_client.delete_object(
        Bucket=settings.NEON_STORAGE_BUCKET,
        Key=object_key
    )


def download_file(object_key: str):
    """Download an object from Neon Object Storage."""

    response = s3_client.get_object(
        Bucket=settings.NEON_STORAGE_BUCKET,
        Key=object_key
    )

    try:
        return response["Body"].read()
    finally:
        response["Body"].close()

        
