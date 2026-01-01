#!/usr/bin/env python3
"""
Scrape PostgreSQL mailing list emails into DuckDB with Iceberg extension.
"""

import duckdb
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

DATABASE_PATH = "postgres_mailing_lists.duckdb"
BASE_URL = "https://www.postgresql.org"
LIST_URL = f"{BASE_URL}/list/pgsql-hackers/"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}


def init_database(db_path: str) -> duckdb.DuckDBPyConnection:
    """Initialize DuckDB database."""
    conn = duckdb.connect(db_path)

    # Try to install iceberg extension (optional, may fail in restricted environments)
    try:
        conn.execute("INSTALL iceberg;")
        conn.execute("LOAD iceberg;")
        print("Iceberg extension loaded")
    except Exception as e:
        print(f"Iceberg extension not available: {e}")

    # Create messages table
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


def fetch_page(url: str) -> str:
    """Fetch a page with proper headers."""
    print(f"Fetching: {url}")
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    time.sleep(1)  # Be polite
    return response.text


def parse_list_page(html: str) -> list[dict]:
    """Parse the mailing list index page to get message links."""
    soup = BeautifulSoup(html, 'html.parser')
    messages = []

    # Find message rows - they're in a table or list structure
    # Looking for links that go to /message-id/
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if '/message-id/' in href:
            messages.append({
                'url': BASE_URL + href if href.startswith('/') else href,
                'subject': link.get_text(strip=True)
            })

    return messages


def parse_message_page(html: str, url: str) -> dict:
    """Parse an individual message page."""
    soup = BeautifulSoup(html, 'html.parser')

    message = {
        'url': url,
        'id': url.split('/')[-1] if url else None,
    }

    # Try to find message metadata
    # The PostgreSQL archive has specific structure

    # Subject
    subject_elem = soup.find('h1') or soup.find('title')
    message['subject'] = subject_elem.get_text(strip=True) if subject_elem else ''

    # Look for message headers (From, Date, etc.)
    for th in soup.find_all('th'):
        text = th.get_text(strip=True).lower()
        td = th.find_next_sibling('td')
        if td:
            value = td.get_text(strip=True)
            if 'from' in text:
                message['author'] = value
            elif 'date' in text:
                message['date'] = value
            elif 'message-id' in text:
                message['message_id'] = value

    # Message body - look for pre or main content area
    body = soup.find('pre') or soup.find('div', class_='message-body') or soup.find('main')
    message['content'] = body.get_text() if body else ''

    return message


def scrape_messages(conn: duckdb.DuckDBPyConnection, limit: int = 10):
    """Scrape messages from the mailing list."""

    # Fetch the list page
    try:
        list_html = fetch_page(LIST_URL)
    except Exception as e:
        print(f"Failed to fetch list page: {e}")
        return 0

    # Parse to get message links
    message_links = parse_list_page(list_html)
    print(f"Found {len(message_links)} message links")

    if not message_links:
        print("No messages found on list page")
        return 0

    # Fetch individual messages
    scraped = 0
    for msg_info in message_links[:limit]:
        try:
            msg_html = fetch_page(msg_info['url'])
            message = parse_message_page(msg_html, msg_info['url'])

            # Use subject from list page if not found in message
            if not message.get('subject'):
                message['subject'] = msg_info.get('subject', '')

            # Parse date if present
            date_parsed = None
            if message.get('date'):
                try:
                    # Try common date formats
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%a, %d %b %Y %H:%M:%S %z', '%d %b %Y %H:%M:%S']:
                        try:
                            date_parsed = datetime.strptime(message['date'][:25], fmt)
                            break
                        except:
                            continue
                except:
                    pass

            # Insert into database
            conn.execute("""
                INSERT OR REPLACE INTO messages
                (id, message_id, subject, author, date, date_parsed, content, url, list_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                message.get('id'),
                message.get('message_id'),
                message.get('subject'),
                message.get('author'),
                message.get('date'),
                date_parsed,
                message.get('content'),
                message.get('url'),
                'pgsql-hackers'
            ])

            scraped += 1
            print(f"  Scraped: {message.get('subject', 'No subject')[:60]}...")

        except Exception as e:
            print(f"  Failed to scrape {msg_info['url']}: {e}")
            continue

    conn.commit()
    return scraped


def main():
    print("Initializing DuckDB with Iceberg extension...")
    conn = init_database(DATABASE_PATH)

    print(f"\nScraping pgsql-hackers mailing list...")
    count = scrape_messages(conn, limit=10)

    print(f"\nScraped {count} messages")

    # Show results
    print("\n" + "="*80)
    print("SAMPLE DATA:")
    print("="*80)

    result = conn.execute("""
        SELECT id, subject, author, date, length(content) as content_length
        FROM messages
        LIMIT 10
    """).fetchall()

    for row in result:
        print(f"\nID: {row[0]}")
        print(f"Subject: {row[1]}")
        print(f"Author: {row[2]}")
        print(f"Date: {row[3]}")
        print(f"Content Length: {row[4]} chars")

    conn.close()
    print(f"\nDatabase saved to: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
