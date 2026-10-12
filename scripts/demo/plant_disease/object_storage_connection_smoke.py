from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
from minio import Minio


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = json.loads(arguments.manifest.read_bytes())
    sample = manifest["cases"][0]
    image_path = arguments.manifest.parent / sample["image_file"]
    image = image_path.read_bytes()
    image_sha256 = sha256(image).hexdigest()
    if image_sha256 != sample["image_sha256"]:
        raise ValueError("plantdoc_storage_image_checksum_mismatch")

    client = Minio(
        os.environ["IOAP_MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=os.environ["IOAP_MINIO_SECURE"].casefold() == "true",
    )
    bucket = os.environ["IOAP_MINIO_BUCKET"]
    if not client.bucket_exists(bucket):
        raise RuntimeError("plantdoc_storage_bucket_missing")

    prefix = f"plant-disease-validation/{uuid4().hex}"
    object_key = f"{prefix}/source-image.jpg"
    signed_put_key = f"{prefix}/signed-put-image.jpg"
    client.put_object(
        bucket,
        object_key,
        BytesIO(image),
        length=len(image),
        content_type="image/jpeg",
    )
    try:
        metadata = client.stat_object(bucket, object_key)
        if metadata.size != len(image):
            raise RuntimeError("plantdoc_storage_head_size_mismatch")
        response = client.get_object(bucket, object_key)
        try:
            downloaded = response.read()
        finally:
            response.close()
            response.release_conn()
        if sha256(downloaded).hexdigest() != image_sha256:
            raise RuntimeError("plantdoc_storage_download_checksum_mismatch")

        async with httpx.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            timeout=30,
        ) as session:
            signed_get_url = client.get_presigned_url("GET", bucket, object_key)
            signed_get = await session.get(signed_get_url)
            if (
                signed_get.status_code != 200
                or sha256(signed_get.content).hexdigest() != image_sha256
            ):
                raise RuntimeError("plantdoc_storage_presigned_get_failed")
            signed_put_url = client.get_presigned_url(
                "PUT",
                bucket,
                signed_put_key,
                expires=timedelta(minutes=1),
            )
            signed_put = await session.put(signed_put_url, content=image)
            if signed_put.status_code != 200:
                raise RuntimeError("plantdoc_storage_presigned_put_failed")

        signed_response = client.get_object(bucket, signed_put_key)
        try:
            signed_download = signed_response.read()
        finally:
            signed_response.close()
            signed_response.release_conn()
        if sha256(signed_download).hexdigest() != image_sha256:
            raise RuntimeError("plantdoc_storage_presigned_put_checksum_mismatch")
    finally:
        client.remove_object(bucket, object_key)
        client.remove_object(bucket, signed_put_key)

    print(
        json.dumps(
            {
                "bucket_exists": True,
                "put_get_head_delete": "PASS",
                "presigned_get": "PASS",
                "presigned_put": "PASS",
                "source_image_sha256": image_sha256,
                "source_image_bytes": len(image),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
