#!/usr/bin/env python3
"""
Step 2: Create namespace and table in Supabase Iceberg bucket.

This script sets up the Iceberg catalog structure in Supabase Analytics Buckets.

Required environment variables (from .env):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    TOKEN
    WAREHOUSE
    S3_ENDPOINT
    CATALOG_URI

Usage:
    # Set up environment
    cp .env.example .env
    # Edit .env with your Supabase credentials

    # Run setup
    uv run 02_setup_iceberg.py
"""

import os
import sys

from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    IntegerType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)

# Load environment variables from .env file
load_dotenv()

# Configuration from environment
CATALOG_URI = os.environ.get("CATALOG_URI")
WAREHOUSE = os.environ.get("WAREHOUSE")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
TOKEN = os.environ.get("TOKEN")

NAMESPACE = "postgres_mailing_lists"
TABLE_NAME = "messages"

# Schema for mailing list messages
MESSAGES_SCHEMA = Schema(
    NestedField(1, "id", StringType(), required=True),
    NestedField(2, "message_id", StringType(), required=False),
    NestedField(3, "subject", StringType(), required=False),
    NestedField(4, "author", StringType(), required=False),
    NestedField(5, "date", StringType(), required=False),
    NestedField(6, "date_parsed", TimestampType(), required=False),
    NestedField(7, "content", StringType(), required=False),
    NestedField(8, "url", StringType(), required=False),
    NestedField(9, "thread_id", StringType(), required=False),
    NestedField(10, "list_name", StringType(), required=False),
    NestedField(11, "crawled_at", TimestampType(), required=False),
)


def check_env():
    """Verify all required environment variables are set."""
    required = [
        "CATALOG_URI",
        "WAREHOUSE",
        "S3_ENDPOINT",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "TOKEN",
    ]

    missing = [var for var in required if not os.environ.get(var)]

    if missing:
        print("ERROR: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nCopy .env.example to .env and fill in your Supabase credentials.")
        sys.exit(1)


def get_catalog():
    """Initialize the Iceberg catalog."""
    return load_catalog(
        "supabase",
        type="rest",
        uri=CATALOG_URI,
        token=TOKEN,
        warehouse=WAREHOUSE,
        **{
            "s3.endpoint": S3_ENDPOINT,
            "s3.access-key-id": AWS_ACCESS_KEY_ID,
            "s3.secret-access-key": AWS_SECRET_ACCESS_KEY,
            "s3.region": "auto",
            "s3.path-style-access": "true",
        },
    )


def setup_namespace(catalog):
    """Create the namespace if it doesn't exist."""
    print(f"\nChecking namespace: {NAMESPACE}")

    existing = [ns[0] for ns in catalog.list_namespaces()]

    if NAMESPACE in existing:
        print(f"  ✓ Namespace '{NAMESPACE}' already exists")
    else:
        print(f"  Creating namespace '{NAMESPACE}'...")
        catalog.create_namespace(
            NAMESPACE,
            properties={
                "description": "PostgreSQL mailing list archives",
                "source": "https://www.postgresql.org/list/",
            },
        )
        print(f"  ✓ Namespace '{NAMESPACE}' created")

    return NAMESPACE


def setup_table(catalog, namespace):
    """Create the messages table if it doesn't exist."""
    table_identifier = f"{namespace}.{TABLE_NAME}"
    print(f"\nChecking table: {table_identifier}")

    existing = [t[1] for t in catalog.list_tables(namespace)]

    if TABLE_NAME in existing:
        print(f"  ✓ Table '{TABLE_NAME}' already exists")
        table = catalog.load_table(table_identifier)
        print(f"  Schema: {table.schema()}")
    else:
        print(f"  Creating table '{TABLE_NAME}'...")
        table = catalog.create_table(
            table_identifier,
            schema=MESSAGES_SCHEMA,
        )
        print(f"  ✓ Table '{TABLE_NAME}' created")
        print(f"  Schema: {table.schema()}")

    return table


def show_catalog_info(catalog):
    """Display catalog information."""
    print("\n" + "=" * 70)
    print("ICEBERG CATALOG INFO")
    print("=" * 70)

    print(f"\nCatalog URI: {CATALOG_URI}")
    print(f"Warehouse: {WAREHOUSE}")
    print(f"S3 Endpoint: {S3_ENDPOINT}")

    print("\nNamespaces:")
    for ns in catalog.list_namespaces():
        print(f"  - {ns[0]}")
        for table in catalog.list_tables(ns[0]):
            print(f"      └── {table[1]}")


def main():
    print("=" * 70)
    print("Supabase Iceberg Setup - PostgreSQL Mailing Lists")
    print("=" * 70)

    # Check environment
    check_env()

    # Initialize catalog
    print("\nConnecting to Iceberg catalog...")
    catalog = get_catalog()
    print("  ✓ Connected")

    # Setup namespace and table
    namespace = setup_namespace(catalog)
    table = setup_table(catalog, namespace)

    # Show info
    show_catalog_info(catalog)

    print("\n" + "=" * 70)
    print("Setup complete! You can now run 03_scrape_iceberg.py to populate data.")
    print("=" * 70)


if __name__ == "__main__":
    main()
