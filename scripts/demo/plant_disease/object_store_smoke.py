from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import timedelta
from hashlib import sha256
from pathlib import Path

import httpx
from minio import Minio
from minio.error import S3Error

from industrial_ops_agent.object_store.keys import ObjectZone, application_object_key
from industrial_ops_agent.object_store.minio import MinioTenantObjectStore
from industrial_ops_agent.persistence.tenant import TenantContext


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_bytes())
    sample = manifest["cases"][0]
    image_path = args.manifest.parent / sample["image_file"]
    content = image_path.read_bytes()
    content_hash = sha256(content).hexdigest()
    if content_hash != sample["image_sha256"]:
        raise ValueError("plantdoc_storage_image_checksum_mismatch")

    endpoint = os.environ["IOAP_MINIO_ENDPOINT"]
    secure = os.environ["IOAP_MINIO_SECURE"].casefold() == "true"
    access_key = os.environ["MINIO_ROOT_USER"]
    secret_key = os.environ["MINIO_ROOT_PASSWORD"]
    bucket = os.environ["IOAP_MINIO_BUCKET"]
    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
    if not client.bucket_exists(bucket):
        raise RuntimeError("plantdoc_storage_bucket_missing")

    context = TenantContext(
        tenant_id="tenant-m1-demo",
        subject_id="subject-m1-engineer",
    )
    application_id = "plant-disease"
    application_context_id = "source-review-smoke"
    interface_key = application_object_key(
        context,
        ObjectZone.CLEAN,
        application_id=application_id,
        application_context_id=application_context_id,
        media_id="manifest-image",
    )
    signed_put_key = application_object_key(
        context,
        ObjectZone.CLEAN,
        application_id=application_id,
        application_context_id=application_context_id,
        media_id="signed-put-image",
    )
    store = MinioTenantObjectStore(client, bucket)
    await store.put(context, interface_key, content)
    metadata = client.stat_object(bucket, interface_key.value)
    if metadata.size != len(content):
        raise RuntimeError("plantdoc_storage_head_size_mismatch")
    stored = await store.get(context, interface_key)
    if stored != content:
        raise RuntimeError("plantdoc_storage_interface_read_mismatch")

    get_url = client.get_presigned_url("GET", bucket, interface_key.value)
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=30) as session:
        signed_get = await session.get(get_url)
        if signed_get.status_code != 200 or signed_get.content != content:
            raise RuntimeError("plantdoc_storage_presigned_get_failed")
        put_url = client.get_presigned_url(
            "PUT", bucket, signed_put_key.value, expires=timedelta(minutes=1)
        )
        signed_put = await session.put(put_url, content=content)
        if signed_put.status_code != 200:
            raise RuntimeError("plantdoc_storage_presigned_put_failed")

    signed_put_content = await store.get(context, signed_put_key)
    if signed_put_content != content:
        raise RuntimeError("plantdoc_storage_presigned_put_read_mismatch")
    await store.delete(context, interface_key)
    await store.delete(context, signed_put_key)
    for key in (interface_key, signed_put_key):
        try:
            client.stat_object(bucket, key.value)
        except S3Error as exc:
            if exc.code not in {"NoSuchKey", "NoSuchObject"}:
                raise
        else:
            raise RuntimeError("plantdoc_storage_delete_failed")

    print(
        json.dumps(
            {
                "bucket_exists": True,
                "put_get_head_delete": "PASS",
                "presigned_get": "PASS",
                "presigned_put": "PASS",
                "source_image_sha256": content_hash,
                "source_image_bytes": len(content),
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
