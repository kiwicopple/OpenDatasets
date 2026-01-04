#!/usr/bin/env python3
"""
Step 1: Scrape Hacker News to local DuckDB for verification.

This script uses the official Hacker News API (no API key required)
to fetch stories and comments, storing them in a local DuckDB database.

API Documentation: https://github.com/HackerNews/API

Usage:
    # Scrape top stories (default: 10)
    uv run --with requests --with duckdb 01_scrape_local.py

    # Scrape more stories
    uv run --with requests --with duckdb 01_scrape_local.py --limit 50

    # Scrape specific type (top, new, best, ask, show, job)
    uv run --with requests --with duckdb 01_scrape_local.py --type best --limit 20
"""

import argparse
import os
import time
from datetime import datetime

import duckdb
import requests

# Configuration
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "hackernews.duckdb")

API_BASE = "https://hacker-news.firebaseio.com/v0"

STORY_TYPES = {
    "top": "topstories",
    "new": "newstories",
    "best": "beststories",
    "ask": "askstories",
    "show": "showstories",
    "job": "jobstories",
}


def init_database(conn: duckdb.DuckDBPyConnection):
    """Initialize the database schema."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id BIGINT PRIMARY KEY,
            type VARCHAR,
            by VARCHAR,
            time BIGINT,
            time_parsed TIMESTAMP,
            title VARCHAR,
            url VARCHAR,
            text VARCHAR,
            score INTEGER,
            descendants INTEGER,
            parent BIGINT,
            kids BIGINT[],
            story_type VARCHAR,
            crawled_at TIMESTAMP
        )
    """)
    print(f"  ✓ Database initialized: {DB_PATH}")


def fetch_item(item_id: int, delay: float = 0.1) -> dict | None:
    """Fetch a single item from the HN API."""
    url = f"{API_BASE}/item/{item_id}.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        time.sleep(delay)  # Rate limiting
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


def insert_item(conn: duckdb.DuckDBPyConnection, item: dict, story_type: str):
    """Insert an item into the database."""
    now = datetime.utcnow()
    time_parsed = datetime.fromtimestamp(item.get("time", 0)) if item.get("time") else None

    conn.execute("""
        INSERT OR REPLACE INTO items
        (id, type, by, time, time_parsed, title, url, text, score,
         descendants, parent, kids, story_type, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        item.get("id"),
        item.get("type"),
        item.get("by"),
        item.get("time"),
        time_parsed,
        item.get("title"),
        item.get("url"),
        item.get("text"),
        item.get("score"),
        item.get("descendants"),
        item.get("parent"),
        item.get("kids"),
        story_type,
        now,
    ])


def scrape_stories(conn: duckdb.DuckDBPyConnection, story_type: str, limit: int):
    """Scrape stories from Hacker News."""
    print(f"\nFetching {story_type} story IDs...")
    story_ids = fetch_story_ids(story_type)
    print(f"  Found {len(story_ids)} stories")

    stories_to_fetch = story_ids[:limit]
    fetched = 0

    for i, story_id in enumerate(stories_to_fetch):
        print(f"  [{i+1}/{len(stories_to_fetch)}] Fetching story {story_id}...", end="")

        item = fetch_item(story_id)
        if item:
            insert_item(conn, item, story_type)
            title = item.get("title", "")[:50]
            print(f" ✓ {title}...")
            fetched += 1
        else:
            print(" ✗ Failed")

    return fetched


def main():
    parser = argparse.ArgumentParser(description="Scrape Hacker News to local DuckDB")
    parser.add_argument("--limit", type=int, default=10, help="Max stories to scrape")
    parser.add_argument("--type", choices=list(STORY_TYPES.keys()), default="top",
                       help="Type of stories to scrape")
    args = parser.parse_args()

    print("=" * 70)
    print("Hacker News Scraper - Local DuckDB")
    print("=" * 70)

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Connect to database
    print(f"\nConnecting to database: {DB_PATH}")
    conn = duckdb.connect(DB_PATH)
    init_database(conn)

    # Scrape
    fetched = scrape_stories(conn, args.type, args.limit)

    # Summary
    result = conn.execute("SELECT COUNT(*) FROM items").fetchone()
    total = result[0] if result else 0

    print("\n" + "=" * 70)
    print(f"SUCCESS: Scraped {fetched} stories")
    print(f"Total items in database: {total}")
    print("=" * 70)

    # Show sample
    print("\nSample data:")
    sample = conn.execute("""
        SELECT id, type, title, score, by
        FROM items
        WHERE title IS NOT NULL
        ORDER BY crawled_at DESC
        LIMIT 5
    """).fetchall()

    for row in sample:
        print(f"  [{row[0]}] ({row[1]}) {row[2][:40]}... score={row[3]} by={row[4]}")

    conn.close()


if __name__ == "__main__":
    main()
