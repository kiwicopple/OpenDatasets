"""
Supabase Vector Bucket operations.

Vector Buckets store embeddings alongside content in Parquet format,
optimized for similarity search via Edge Functions.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.config import Config


@dataclass
class VectorClient:
    """
    Client for Supabase Vector Buckets.

    Vector Buckets are S3-compatible storage for embeddings in Parquet format.

    Example:
        client = VectorClient(
            s3_endpoint="https://<project>.supabase.co/storage/v1/s3",
            access_key="your-access-key",
            secret_key="your-secret-key",
            bucket="vector-bucket",
        )

        # Write embeddings
        client.write_embeddings("my-dataset", "v1.0.0", arrow_table)

        # Read embeddings
        table = client.read_embeddings("my-dataset", "v1.0.0")
    """

    s3_endpoint: str = field(default_factory=lambda: os.environ.get("SUPABASE_S3_ENDPOINT", ""))
    access_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_ACCESS_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SECRET_KEY", ""))
    bucket: str = "vector-bucket"
    region: str = "auto"

    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if not all([self.s3_endpoint, self.access_key, self.secret_key]):
            raise ValueError(
                "Missing required configuration. Set environment variables: "
                "SUPABASE_S3_ENDPOINT, SUPABASE_ACCESS_KEY, SUPABASE_SECRET_KEY"
            )

    @property
    def client(self):
        """Lazy-load the S3 client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.s3_endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def _get_key(self, dataset: str, version: str, filename: str) -> str:
        """Build S3 key for a file."""
        return f"{dataset}/{version}/{filename}"

    def write_embeddings(
        self,
        dataset: str,
        version: str,
        data: pa.Table,
        compression: str = "zstd",
    ):
        """
        Write embeddings to Vector Bucket.

        Args:
            dataset: Dataset name
            version: Version string (e.g., "v2024.12.1")
            data: PyArrow Table with embeddings
            compression: Parquet compression (zstd, snappy, gzip)
        """
        import io

        # Write to buffer
        buffer = io.BytesIO()
        pq.write_table(data, buffer, compression=compression)
        buffer.seek(0)

        # Upload to S3
        key = self._get_key(dataset, version, "embeddings.parquet")
        self.client.upload_fileobj(buffer, self.bucket, key)

        # Write manifest
        manifest = {
            "dataset": dataset,
            "version": version,
            "row_count": data.num_rows,
            "columns": data.column_names,
            "created_at": datetime.utcnow().isoformat(),
            "compression": compression,
        }
        manifest_key = self._get_key(dataset, version, "manifest.json")
        self.client.put_object(
            Bucket=self.bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, indent=2),
            ContentType="application/json",
        )

    def read_embeddings(self, dataset: str, version: str) -> pa.Table:
        """
        Read embeddings from Vector Bucket.

        Args:
            dataset: Dataset name
            version: Version string

        Returns:
            PyArrow Table with embeddings
        """
        import io

        key = self._get_key(dataset, version, "embeddings.parquet")
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        buffer = io.BytesIO(response["Body"].read())
        return pq.read_table(buffer)

    def read_manifest(self, dataset: str, version: str) -> dict:
        """Read dataset manifest."""
        key = self._get_key(dataset, version, "manifest.json")
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return json.loads(response["Body"].read())

    def list_versions(self, dataset: str) -> list[str]:
        """List all versions of a dataset."""
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=f"{dataset}/",
            Delimiter="/",
        )
        versions = []
        for prefix in response.get("CommonPrefixes", []):
            version = prefix["Prefix"].split("/")[-2]
            versions.append(version)
        return sorted(versions, reverse=True)

    def list_datasets(self) -> list[str]:
        """List all datasets in the bucket."""
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Delimiter="/",
        )
        datasets = []
        for prefix in response.get("CommonPrefixes", []):
            dataset = prefix["Prefix"].rstrip("/")
            datasets.append(dataset)
        return datasets

    def delete_version(self, dataset: str, version: str):
        """Delete a specific version of a dataset."""
        prefix = f"{dataset}/{version}/"
        response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)

        for obj in response.get("Contents", []):
            self.client.delete_object(Bucket=self.bucket, Key=obj["Key"])

    def get_download_url(self, dataset: str, version: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for downloading embeddings.

        Args:
            dataset: Dataset name
            version: Version string
            expires_in: URL expiration in seconds

        Returns:
            Presigned URL
        """
        key = self._get_key(dataset, version, "embeddings.parquet")
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )


def create_embeddings_table(
    chunks: list[dict],
    embeddings: list[list[float]],
) -> pa.Table:
    """
    Create a PyArrow table for embeddings.

    Args:
        chunks: List of chunk dictionaries with keys:
            - chunk_id, doc_id, content, chunk_index, source_url, license, metadata
        embeddings: List of embedding vectors

    Returns:
        PyArrow Table ready for Vector Bucket
    """
    return pa.table({
        "chunk_id": [c["chunk_id"] for c in chunks],
        "doc_id": [c["doc_id"] for c in chunks],
        "content": [c["content"] for c in chunks],
        "chunk_index": [c["chunk_index"] for c in chunks],
        "source_url": [c.get("source_url", "") for c in chunks],
        "license": [c.get("license", "") for c in chunks],
        "embedding": embeddings,
        "metadata": [json.dumps(c.get("metadata", {})) for c in chunks],
        "created_at": [datetime.utcnow()] * len(chunks),
    })
