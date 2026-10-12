from __future__ import annotations

import os

from minio import Minio


def main() -> None:
    client = Minio(
        os.environ["IOAP_MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ROOT_USER"],
        secret_key=os.environ["MINIO_ROOT_PASSWORD"],
        secure=os.environ["IOAP_MINIO_SECURE"].casefold() == "true",
        region="us-east-1",
    )
    for bucket in ("industrial-ops-media", "industrial-ops-datasets"):
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket, location="us-east-1")


if __name__ == "__main__":
    main()
