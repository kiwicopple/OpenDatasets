#!/usr/bin/env python3
"""
Step 1: Scrape PostgreSQL mailing list to local DuckDB for verification.

This script scrapes the pgsql-hackers mailing list and stores results
in a local DuckDB database for inspection before uploading to Supabase.

Usage:
    uv run 01_scrape_local.py

Output:
    ./data/messages.duckdb
"""

import os
import time
from datetime import datetime
from pathlib import Path

import duckdb
import requests
from bs4 import BeautifulSoup

# Configuration
DATA_DIR = Path(__file__).parent / "data"
DATABASE_PATH = DATA_DIR / "messages.duckdb"
BASE_URL = "https://www.postgresql.org"
LIST_URL = f"{BASE_URL}/list/pgsql-hackers/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def init_database() -> duckdb.DuckDBPyConnection:
    """Initialize local DuckDB database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(DATABASE_PATH))

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR,
            subject VARCHAR,
            author VARCHAR,
            date VARCHAR,
            date_parsed TIMESTAMP,
            content TEXT,
            url VARCHAR,
            thread_id VARCHAR,
            list_name VARCHAR DEFAULT 'pgsql-hackers',
            crawled_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    return conn


def fetch_page(url: str, delay: float = 1.0) -> str:
    """Fetch a page with rate limiting."""
    print(f"  Fetching: {url}")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    time.sleep(delay)
    return response.text


def parse_list_page(html: str) -> list[dict]:
    """Parse the mailing list index page to get message links."""
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
        "url": url,
        "id": url.split("/")[-1] if url else None,
    }

    # Subject from h1 or title
    subject_elem = soup.find("h1") or soup.find("title")
    message["subject"] = subject_elem.get_text(strip=True) if subject_elem else ""

    # Extract headers from table
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

    # Message body
    body = soup.find("pre") or soup.find("div", class_="message-body") or soup.find("main")
    message["content"] = body.get_text() if body else ""

    return message


def scrape_messages(conn: duckdb.DuckDBPyConnection, limit: int = 10) -> int:
    """Scrape messages from the mailing list."""
    print(f"\nFetching list page: {LIST_URL}")

    try:
        list_html = fetch_page(LIST_URL)
    except Exception as e:
        print(f"Failed to fetch list page: {e}")
        return 0

    message_links = parse_list_page(list_html)
    print(f"Found {len(message_links)} message links")

    if not message_links:
        return 0

    scraped = 0
    for msg_info in message_links[:limit]:
        try:
            msg_html = fetch_page(msg_info["url"])
            message = parse_message_page(msg_html, msg_info["url"])

            if not message.get("subject"):
                message["subject"] = msg_info.get("subject", "")

            # Insert into database
            conn.execute("""
                INSERT OR REPLACE INTO messages
                (id, message_id, subject, author, date, content, url, list_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                message.get("id"),
                message.get("message_id"),
                message.get("subject"),
                message.get("author"),
                message.get("date"),
                message.get("content"),
                message.get("url"),
                "pgsql-hackers",
            ])

            scraped += 1
            print(f"  ✓ {message.get('subject', 'No subject')[:60]}...")

        except Exception as e:
            print(f"  ✗ Failed: {msg_info['url']}: {e}")
            continue

    conn.commit()
    return scraped


def show_results(conn: duckdb.DuckDBPyConnection):
    """Display scraped data summary."""
    print("\n" + "=" * 70)
    print("LOCAL DATABASE SUMMARY")
    print("=" * 70)

    count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    print(f"\nTotal messages: {count}")

    if count > 0:
        print("\nRecent messages:")
        print("-" * 70)

        results = conn.execute("""
            SELECT subject, author, date
            FROM messages
            ORDER BY crawled_at DESC
            LIMIT 5
        """).fetchall()

        for row in results:
            print(f"  Subject: {row[0][:50]}...")
            print(f"  Author:  {row[1]}")
            print(f"  Date:    {row[2]}")
            print()

    print(f"Database saved to: {DATABASE_PATH}")


def main():
    print("=" * 70)
    print("PostgreSQL Mailing List Scraper - Local DuckDB")
    print("=" * 70)

    conn = init_database()

    try:
        count = scrape_messages(conn, limit=10)
        print(f"\nScraped {count} messages")
        show_results(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
