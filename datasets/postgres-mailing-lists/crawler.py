#!/usr/bin/env python3
"""
PostgreSQL Mailing List Crawler using Firecrawl

Crawls the pgsql-hackers mailing list and stores results in DuckDB.
"""

import os
import json
import duckdb
from datetime import datetime
from firecrawl import FirecrawlApp

# Configuration
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")
DATABASE_PATH = "postgres_mailing_lists.duckdb"
BASE_URL = "https://www.postgresql.org/list/pgsql-hackers/"


def init_database(db_path: str) -> duckdb.DuckDBPyConnection:
    """Initialize DuckDB database with schema."""
    conn = duckdb.connect(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR,
            subject VARCHAR,
            author_name VARCHAR,
            author_email VARCHAR,
            date TIMESTAMP,
            content TEXT,
            url VARCHAR,
            in_reply_to VARCHAR,
            list_name VARCHAR DEFAULT 'pgsql-hackers',
            crawled_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS crawl_metadata (
            id INTEGER PRIMARY KEY,
            crawl_started_at TIMESTAMP,
            crawl_finished_at TIMESTAMP,
            pages_crawled INTEGER,
            messages_extracted INTEGER,
            status VARCHAR
        )
    """)

    return conn


def crawl_mailing_list(app: FirecrawlApp, url: str, limit: int = 10):
    """Crawl the mailing list archive."""

    print(f"Starting crawl of {url}")

    # Use Firecrawl to crawl the mailing list
    result = app.crawl_url(
        url,
        params={
            'limit': limit,
            'scrapeOptions': {
                'formats': ['markdown', 'html'],
            }
        },
        poll_interval=5
    )

    return result


def extract_messages_from_crawl(crawl_data: dict) -> list[dict]:
    """Extract individual messages from crawl results."""
    messages = []

    for page in crawl_data.get('data', []):
        url = page.get('metadata', {}).get('url', '')

        # Check if this is an individual message page (has message-id in URL)
        if '/message-id/' in url or 'flat/' in url:
            message = {
                'id': url.split('/')[-1] if url else None,
                'url': url,
                'subject': page.get('metadata', {}).get('title', ''),
                'content': page.get('markdown', ''),
                'html': page.get('html', ''),
                'crawled_at': datetime.now().isoformat()
            }

            # Try to extract author and date from content
            # This is a simplified extraction - real implementation would parse more carefully
            metadata = page.get('metadata', {})
            message['author_name'] = metadata.get('author', '')
            message['date'] = metadata.get('date', '')

            messages.append(message)
        else:
            # This is a list page - extract links to individual messages
            print(f"Found list page: {url}")

    return messages


def save_to_duckdb(conn: duckdb.DuckDBPyConnection, messages: list[dict]):
    """Save extracted messages to DuckDB."""

    for msg in messages:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO messages (id, subject, author_name, content, url, crawled_at, list_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                msg.get('id'),
                msg.get('subject'),
                msg.get('author_name'),
                msg.get('content'),
                msg.get('url'),
                msg.get('crawled_at'),
                'pgsql-hackers'
            ])
        except Exception as e:
            print(f"Error saving message {msg.get('id')}: {e}")

    conn.commit()


def main():
    """Main entry point."""

    if not FIRECRAWL_API_KEY:
        print("Error: FIRECRAWL_API_KEY environment variable not set")
        print("Get your API key from https://firecrawl.dev")
        return

    # Initialize Firecrawl
    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

    # Initialize database
    conn = init_database(DATABASE_PATH)

    # Record crawl start
    crawl_id = conn.execute("""
        INSERT INTO crawl_metadata (crawl_started_at, status)
        VALUES (current_timestamp, 'running')
        RETURNING id
    """).fetchone()[0]

    try:
        # Crawl the mailing list
        crawl_result = crawl_mailing_list(app, BASE_URL, limit=20)

        # Save raw crawl result for debugging
        with open('crawl_result.json', 'w') as f:
            json.dump(crawl_result, f, indent=2, default=str)

        print(f"Crawl completed. Got {len(crawl_result.get('data', []))} pages")

        # Extract messages
        messages = extract_messages_from_crawl(crawl_result)
        print(f"Extracted {len(messages)} messages")

        # Save to DuckDB
        save_to_duckdb(conn, messages)

        # Update crawl metadata
        conn.execute("""
            UPDATE crawl_metadata
            SET crawl_finished_at = current_timestamp,
                pages_crawled = ?,
                messages_extracted = ?,
                status = 'completed'
            WHERE id = ?
        """, [len(crawl_result.get('data', [])), len(messages), crawl_id])

    except Exception as e:
        print(f"Crawl failed: {e}")
        conn.execute("""
            UPDATE crawl_metadata
            SET crawl_finished_at = current_timestamp,
                status = 'failed'
            WHERE id = ?
        """, [crawl_id])
        raise

    finally:
        conn.close()

    print(f"Done! Data saved to {DATABASE_PATH}")
    print("\nTo query the data:")
    print(f"  duckdb {DATABASE_PATH}")
    print("  SELECT * FROM messages LIMIT 5;")


if __name__ == "__main__":
    main()
