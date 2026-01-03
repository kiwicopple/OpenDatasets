#!/usr/bin/env python3
"""
Step 3: Scrape PostgreSQL mailing list directly to Supabase Iceberg bucket.

This script scrapes the pgsql-hackers mailing list and writes data
directly to the Supabase Analytics Bucket (Iceberg).

Required environment variables (from .env):
    AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY
    TOKEN
    WAREHOUSE
    S3_ENDPOINT
    CATALOG_URI

Usage:
    # Make sure you've run 02_setup_iceberg.py first!

    # Scrape to remote
    uv run 03_scrape_iceberg.py

    # Scrape with custom limit
    uv run 03_scrape_iceberg.py --limit 50
"""

import argparse
import os
import sys
import time
from datetime import datetime

import pyarrow as pa
import requests
from bs4 import BeautifulSoup
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

NAMESPACE = "postgres_mailing_lists"
TABLE_NAME = "messages"
TABLE_IDENTIFIER = f"{NAMESPACE}.{TABLE_NAME}"

BASE_URL = "https://www.postgresql.org"
LIST_URL = f"{BASE_URL}/list/pgsql-hackers/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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


def fetch_page(url: str, delay: float = 1.0) -> str:
    """Fetch a page with rate limiting."""
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    time.sleep(delay)
    return response.text


def parse_list_page(html: str) -> list[dict]:
    """Parse the mailing list index page."""
    soup = BeautifulSoup(html, "html.parser")
    messages = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if "/message-id/" in href:
            messages.append({
                "url": BASE_URL + href if href.startswith("/") else href,
                "subject": link.get_text(strip=True),
            })
    return messages


def parse_message_page(html: str, url: str) -> dict:
    """Parse an individual message page."""
    soup = BeautifulSoup(html, "html.parser")

    message = {
        "id": url.split("/")[-1] if url else None,
        "url": url,
        "subject": "",
        "author": "",
        "date": "",
        "message_id": "",
        "content": "",
        "thread_id": None,
        "list_name": "pgsql-hackers",
    }

    # Subject
    subject_elem = soup.find("h1") or soup.find("title")
    if subject_elem:
        message["subject"] = subject_elem.get_text(strip=True)

    # Headers
    for th in soup.find_all("th"):
        text = th.get_text(strip=True).lower()
        td = th.find_next_sibling("td")
        if td:
            value = td.get_text(strip=True)
            if "from" in text:
                message["author"] = value
            elif "date" in text:
                message["date"] = value
            elif "message-id" in text:
                message["message_id"] = value

    # Body
    body = soup.find("pre") or soup.find("div", class_="message-body")
    if body:
        message["content"] = body.get_text()

    return message


def scrape_messages(limit: int = 10) -> list[dict]:
    """Scrape messages from the mailing list."""
    print(f"\nFetching list page: {LIST_URL}")
    list_html = fetch_page(LIST_URL)
    message_links = parse_list_page(list_html)
    print(f"Found {len(message_links)} message links")

    messages = []
    for i, msg_info in enumerate(message_links[:limit]):
        try:
            print(f"  [{i+1}/{min(limit, len(message_links))}] Fetching: {msg_info['url'][:60]}...")
            msg_html = fetch_page(msg_info["url"])
            message = parse_message_page(msg_html, msg_info["url"])

            if not message.get("subject"):
                message["subject"] = msg_info.get("subject", "")

            messages.append(message)
            print(f"       ✓ {message['subject'][:50]}...")

        except Exception as e:
            print(f"       ✗ Failed: {e}")
            continue

    return messages


def messages_to_arrow(messages: list[dict]) -> pa.Table:
    """Convert messages to PyArrow table."""
    now = datetime.utcnow()

    return pa.table({
        "id": [m["id"] for m in messages],
        "message_id": [m.get("message_id") for m in messages],
        "subject": [m.get("subject") for m in messages],
        "author": [m.get("author") for m in messages],
        "date": [m.get("date") for m in messages],
        "date_parsed": [None] * len(messages),  # TODO: parse dates
        "content": [m.get("content") for m in messages],
        "url": [m.get("url") for m in messages],
        "thread_id": [m.get("thread_id") for m in messages],
        "list_name": [m.get("list_name", "pgsql-hackers") for m in messages],
        "crawled_at": [now] * len(messages),
    })


def write_to_iceberg(catalog, messages: list[dict]):
    """Write messages to Iceberg table."""
    print(f"\nWriting {len(messages)} messages to Iceberg...")

    table = catalog.load_table(TABLE_IDENTIFIER)
    arrow_table = messages_to_arrow(messages)

    # Append to table
    table.append(arrow_table)

    print(f"  ✓ Written to {TABLE_IDENTIFIER}")

    # Show table info
    scan = table.scan()
    count = len(scan.to_arrow())
    print(f"  Total rows in table: {count}")


def main():
    parser = argparse.ArgumentParser(description="Scrape to Supabase Iceberg")
    parser.add_argument("--limit", type=int, default=10, help="Max messages to scrape")
    args = parser.parse_args()

    print("=" * 70)
    print("PostgreSQL Mailing List Scraper - Supabase Iceberg")
    print("=" * 70)

    check_env()

    print("\nConnecting to Iceberg catalog...")
    catalog = get_catalog()
    print("  ✓ Connected")

    # Verify table exists
    try:
        catalog.load_table(TABLE_IDENTIFIER)
        print(f"  ✓ Table {TABLE_IDENTIFIER} exists")
    except Exception as e:
        print(f"\nERROR: Table {TABLE_IDENTIFIER} not found.")
        print("Run 02_setup_iceberg.py first to create the table.")
        sys.exit(1)

    # Scrape
    messages = scrape_messages(limit=args.limit)

    if messages:
        write_to_iceberg(catalog, messages)
        print("\n" + "=" * 70)
        print(f"SUCCESS: Scraped {len(messages)} messages to Supabase Iceberg")
        print("=" * 70)
    else:
        print("\nNo messages scraped.")


if __name__ == "__main__":
    main()
