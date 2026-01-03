"""
Supabase Analytics Bucket (Iceberg) operations.

Uses PyIceberg to interact with Supabase's Iceberg-compatible storage.
See: https://supabase.com/docs/guides/storage/analytics/examples/pyiceberg
"""

import os
from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    IntegerType,
    ListType,
    FloatType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)


@dataclass
class IcebergClient:
    """
    Client for Supabase Analytics Buckets (Iceberg).

    Example:
        client = IcebergClient(
            catalog_uri="https://<project>.supabase.co/storage/v1/iceberg",
            s3_endpoint="https://<project>.supabase.co/storage/v1/s3",
            access_key="your-access-key",
            secret_key="your-secret-key",
        )

        # Create a table
        client.create_table("my_namespace", "my_table", schema)

        # Write data
        client.append("my_namespace.my_table", arrow_table)
    """

    catalog_uri: str = field(default_factory=lambda: os.environ.get("SUPABASE_ICEBERG_CATALOG_URI", ""))
    s3_endpoint: str = field(default_factory=lambda: os.environ.get("SUPABASE_S3_ENDPOINT", ""))
    access_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_ACCESS_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_SECRET_KEY", ""))
    warehouse: str = "s3://analytics"

    _catalog: Any = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if not all([self.catalog_uri, self.s3_endpoint, self.access_key, self.secret_key]):
            raise ValueError(
                "Missing required configuration. Set environment variables: "
                "SUPABASE_ICEBERG_CATALOG_URI, SUPABASE_S3_ENDPOINT, "
                "SUPABASE_ACCESS_KEY, SUPABASE_SECRET_KEY"
            )

    @property
    def catalog(self):
        """Lazy-load the Iceberg catalog."""
        if self._catalog is None:
            self._catalog = load_catalog(
                "supabase",
                type="rest",
                uri=self.catalog_uri,
                warehouse=self.warehouse,
                **{
                    "s3.endpoint": self.s3_endpoint,
                    "s3.access-key-id": self.access_key,
                    "s3.secret-access-key": self.secret_key,
                    "s3.region": "auto",
                },
            )
        return self._catalog

    def list_namespaces(self) -> list[str]:
        """List all namespaces in the catalog."""
        return [ns[0] for ns in self.catalog.list_namespaces()]

    def list_tables(self, namespace: str) -> list[str]:
        """List all tables in a namespace."""
        return [t[1] for t in self.catalog.list_tables(namespace)]

    def create_namespace(self, namespace: str, properties: dict = None):
        """Create a new namespace."""
        self.catalog.create_namespace(namespace, properties or {})

    def create_table(
        self,
        namespace: str,
        table_name: str,
        schema: Schema,
        partition_spec: Any = None,
    ):
        """
        Create a new Iceberg table.

        Args:
            namespace: Namespace name
            table_name: Table name
            schema: PyIceberg Schema
            partition_spec: Optional partition specification
        """
        identifier = f"{namespace}.{table_name}"

        if partition_spec:
            self.catalog.create_table(identifier, schema, partition_spec=partition_spec)
        else:
            self.catalog.create_table(identifier, schema)

    def load_table(self, identifier: str):
        """Load an existing table."""
        return self.catalog.load_table(identifier)

    def append(self, identifier: str, data: pa.Table):
        """
        Append data to an Iceberg table.

        Args:
            identifier: Table identifier (namespace.table)
            data: PyArrow Table to append
        """
        table = self.load_table(identifier)
        table.append(data)

    def overwrite(self, identifier: str, data: pa.Table):
        """
        Overwrite an Iceberg table with new data.

        Args:
            identifier: Table identifier (namespace.table)
            data: PyArrow Table to write
        """
        table = self.load_table(identifier)
        table.overwrite(data)

    def read(self, identifier: str) -> pa.Table:
        """
        Read all data from an Iceberg table.

        Args:
            identifier: Table identifier (namespace.table)

        Returns:
            PyArrow Table
        """
        table = self.load_table(identifier)
        return table.scan().to_arrow()

    def delete_table(self, identifier: str):
        """Delete a table."""
        self.catalog.drop_table(identifier)


# Common schemas for datasets

MESSAGES_SCHEMA = Schema(
    NestedField(1, "id", StringType(), required=True),
    NestedField(2, "message_id", StringType(), required=False),
    NestedField(3, "subject", StringType(), required=False),
    NestedField(4, "author", StringType(), required=False),
    NestedField(5, "date", TimestampType(), required=False),
    NestedField(6, "content", StringType(), required=False),
    NestedField(7, "url", StringType(), required=False),
    NestedField(8, "thread_id", StringType(), required=False),
    NestedField(9, "list_name", StringType(), required=False),
    NestedField(10, "crawled_at", TimestampType(), required=False),
)

CHUNKS_SCHEMA = Schema(
    NestedField(1, "chunk_id", StringType(), required=True),
    NestedField(2, "doc_id", StringType(), required=True),
    NestedField(3, "content", StringType(), required=True),
    NestedField(4, "chunk_index", IntegerType(), required=True),
    NestedField(5, "source_url", StringType(), required=False),
    NestedField(6, "license", StringType(), required=False),
    NestedField(7, "metadata", StringType(), required=False),  # JSON string
    NestedField(8, "created_at", TimestampType(), required=False),
)

EMBEDDINGS_SCHEMA = Schema(
    NestedField(1, "chunk_id", StringType(), required=True),
    NestedField(2, "doc_id", StringType(), required=True),
    NestedField(3, "content", StringType(), required=True),
    NestedField(4, "chunk_index", IntegerType(), required=True),
    NestedField(5, "source_url", StringType(), required=False),
    NestedField(6, "license", StringType(), required=False),
    NestedField(7, "embedding", ListType(8, FloatType(), element_required=True), required=True),
    NestedField(9, "metadata", StringType(), required=False),
    NestedField(10, "created_at", TimestampType(), required=False),
)
