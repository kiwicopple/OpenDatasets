#!/usr/bin/env python3
"""
Step 2: Create Iceberg namespace and table in Supabase Analytics Bucket.

This script sets up the necessary Iceberg infrastructure for storing
Hacker News data in Supabase.

Required environment variables (from .env):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    TOKEN
    WAREHOUSE
    S3_ENDPOINT
    CATALOG_URI

Usage:
    # First, copy and configure .env
    cp .env.example .env

    # Run setup
    uv run --with pyiceberg --with python-dotenv 02_setup_iceberg.py
"""

import os
import sys

import pyarrow as pa
from dotenv import load_dotenv
from pyiceberg.catalog import load_catalog

# Load environment variables
load_dotenv()

# Configuration
CATALOG_URI = os.environ.get("CATALOG_URI")
WAREHOUSE = os.environ.get("WAREHOUSE")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
TOKEN = os.environ.get("TOKEN")

NAMESPACE = "hackernews"
TABLE_NAME = "items"
TABLE_IDENTIFIER = f"{NAMESPACE}.{TABLE_NAME}"


def check_env():
    """Verify all required environment variables are set."""
    required = [
        "CATALOG_URI", "WAREHOUSE", "S3_ENDPOINT",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "TOKEN",
    ]
    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        print("ERROR: Missing environment variables:", ", ".join(missing))
        print("Run: cp .env.example .env && edit .env")
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


# Schema for Hacker News items
ITEMS_SCHEMA = pa.schema([
    pa.field("id", pa.int64(), nullable=False),
    pa.field("type", pa.string()),
    pa.field("by", pa.string()),
    pa.field("time", pa.int64()),
    pa.field("time_parsed", pa.timestamp("us")),
    pa.field("title", pa.string()),
    pa.field("url", pa.string()),
    pa.field("text", pa.string()),
    pa.field("score", pa.int32()),
    pa.field("descendants", pa.int32()),
    pa.field("parent", pa.int64()),
    pa.field("story_type", pa.string()),
    pa.field("crawled_at", pa.timestamp("us")),
])


def setup_namespace(catalog):
    """Create the namespace if it doesn't exist."""
    print(f"\nChecking namespace: {NAMESPACE}")

    namespaces = [ns[0] for ns in catalog.list_namespaces()]
    if NAMESPACE in namespaces:
        print(f"  ✓ Namespace '{NAMESPACE}' already exists")
    else:
        print(f"  Creating namespace '{NAMESPACE}'...")
        catalog.create_namespace(NAMESPACE)
        print(f"  ✓ Namespace '{NAMESPACE}' created")


def setup_table(catalog):
    """Create the items table if it doesn't exist."""
    print(f"\nChecking table: {TABLE_IDENTIFIER}")

    tables = [t[1] for t in catalog.list_tables(NAMESPACE)]
    if TABLE_NAME in tables:
        print(f"  ✓ Table '{TABLE_IDENTIFIER}' already exists")
        table = catalog.load_table(TABLE_IDENTIFIER)
    else:
        print(f"  Creating table '{TABLE_IDENTIFIER}'...")
        table = catalog.create_table(TABLE_IDENTIFIER, schema=ITEMS_SCHEMA)
        print(f"  ✓ Table '{TABLE_IDENTIFIER}' created")

    return table


def main():
    print("=" * 70)
    print("Hacker News - Supabase Iceberg Setup")
    print("=" * 70)

    check_env()

    print("\nConnecting to Iceberg catalog...")
    catalog = get_catalog()
    print("  ✓ Connected")

    setup_namespace(catalog)
    table = setup_table(catalog)

    # Show table info
    print("\nTable schema:")
    for field in table.schema().fields:
        print(f"  - {field.name}: {field.field_type}")

    print("\n" + "=" * 70)
    print("SUCCESS: Iceberg setup complete")
    print(f"Namespace: {NAMESPACE}")
    print(f"Table: {TABLE_IDENTIFIER}")
    print("=" * 70)


if __name__ == "__main__":
    main()
