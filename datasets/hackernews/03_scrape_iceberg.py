#!/usr/bin/env python3
"""
Step 3: Scrape Hacker News directly to Supabase Iceberg bucket.

This script uses the official Hacker News API to fetch stories
and writes them directly to the Supabase Analytics Bucket (Iceberg).

Required environment variables (from .env):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    TOKEN
    WAREHOUSE
    S3_ENDPOINT
    CATALOG_URI

Usage:
    # Make sure you've run 02_setup_iceberg.py first!

    # Scrape to remote (default: 10 top stories)
    uv run --with pyiceberg --with python-dotenv --with requests 03_scrape_iceberg.py

    # Scrape more stories
    uv run --with pyiceberg --with python-dotenv --with requests 03_scrape_iceberg.py --limit 50

    # Scrape specific type
    uv run --with pyiceberg --with python-dotenv --with requests 03_scrape_iceberg.py --type best --limit 100
"""

import argparse
import os
import sys
import time
from datetime import datetime

import pyarrow as pa
import requests
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

API_BASE = "https://hacker-news.firebaseio.com/v0"

STORY_TYPES = {
    "top": "topstories",
    "new": "newstories",
    "best": "beststories",
    "ask": "askstories",
    "show": "showstories",
    "job": "jobstories",
}


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


def fetch_item(item_id: int, delay: float = 0.1) -> dict | None:
    """Fetch a single item from the HN API."""
    url = f"{API_BASE}/item/{item_id}.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        time.sleep(delay)
        return response.json()
    except Exception as e:
        print(f"       ✗ Failed to fetch item {item_id}: {e}")
        return None


def fetch_story_ids(story_type: str = "top") -> list[int]:
    """Fetch list of story IDs."""
    endpoint = STORY_TYPES.get(story_type, "topstories")
    url = f"{API_BASE}/{endpoint}.json"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def scrape_stories(story_type: str, limit: int) -> list[dict]:
    """Scrape stories from Hacker News."""
    print(f"\nFetching {story_type} story IDs...")
    story_ids = fetch_story_ids(story_type)
    print(f"  Found {len(story_ids)} stories")

    stories_to_fetch = story_ids[:limit]
    items = []

    for i, story_id in enumerate(stories_to_fetch):
        print(f"  [{i+1}/{len(stories_to_fetch)}] Fetching story {story_id}...", end="")

        item = fetch_item(story_id)
        if item:
            item["story_type"] = story_type
            items.append(item)
            title = item.get("title", "")[:50]
            print(f" ✓ {title}...")
        else:
            print(" ✗ Failed")

    return items


def items_to_arrow(items: list[dict]) -> pa.Table:
    """Convert items to PyArrow table."""
    now = datetime.utcnow()

    def parse_time(t):
        return datetime.fromtimestamp(t) if t else None

    return pa.table({
        "id": pa.array([i["id"] for i in items], type=pa.int64()),
        "type": [i.get("type") for i in items],
        "by": [i.get("by") for i in items],
        "time": pa.array([i.get("time") for i in items], type=pa.int64()),
        "time_parsed": [parse_time(i.get("time")) for i in items],
        "title": [i.get("title") for i in items],
        "url": [i.get("url") for i in items],
        "text": [i.get("text") for i in items],
        "score": pa.array([i.get("score") for i in items], type=pa.int32()),
        "descendants": pa.array([i.get("descendants") for i in items], type=pa.int32()),
        "parent": pa.array([i.get("parent") for i in items], type=pa.int64()),
        "story_type": [i.get("story_type") for i in items],
        "crawled_at": [now] * len(items),
    })


def write_to_iceberg(catalog, items: list[dict]):
    """Write items to Iceberg table."""
    print(f"\nWriting {len(items)} items to Iceberg...")

    table = catalog.load_table(TABLE_IDENTIFIER)
    arrow_table = items_to_arrow(items)

    # Append to table
    table.append(arrow_table)

    print(f"  ✓ Written to {TABLE_IDENTIFIER}")

    # Show table info
    scan = table.scan()
    count = len(scan.to_arrow())
    print(f"  Total rows in table: {count}")


def main():
    parser = argparse.ArgumentParser(description="Scrape HN to Supabase Iceberg")
    parser.add_argument("--limit", type=int, default=10, help="Max stories to scrape")
    parser.add_argument("--type", choices=list(STORY_TYPES.keys()), default="top",
                       help="Type of stories to scrape")
    args = parser.parse_args()

    print("=" * 70)
    print("Hacker News Scraper - Supabase Iceberg")
    print("=" * 70)

    check_env()

    print("\nConnecting to Iceberg catalog...")
    catalog = get_catalog()
    print("  ✓ Connected")

    # Verify table exists
    try:
        catalog.load_table(TABLE_IDENTIFIER)
        print(f"  ✓ Table {TABLE_IDENTIFIER} exists")
    except Exception:
        print(f"\nERROR: Table {TABLE_IDENTIFIER} not found.")
        print("Run 02_setup_iceberg.py first to create the table.")
        sys.exit(1)

    # Scrape
    items = scrape_stories(args.type, args.limit)

    if items:
        write_to_iceberg(catalog, items)
        print("\n" + "=" * 70)
        print(f"SUCCESS: Scraped {len(items)} items to Supabase Iceberg")
        print("=" * 70)
    else:
        print("\nNo items scraped.")


if __name__ == "__main__":
    main()
