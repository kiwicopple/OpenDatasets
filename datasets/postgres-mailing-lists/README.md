# PostgreSQL Mailing Lists Dataset

Pre-crawled, chunked PostgreSQL mailing list archives for RAG applications.

## Status

🚧 **In Progress** - Sample data available, production scraper ready for testing

## Quick Start

```bash
# View sample data
python -c "
import duckdb
conn = duckdb.connect('postgres_mailing_lists.duckdb')
print(conn.execute('SELECT subject, author, date FROM messages LIMIT 5').fetchall())
"

# Run the scraper (no API key required)
python scrape_to_duckdb.py
```

## Files

| File | Description |
|------|-------------|
| `postgres_mailing_lists.duckdb` | Sample database with 8 messages |
| `scrape_to_duckdb.py` | Production scraper using requests/BeautifulSoup |
| `create_sample_db.py` | Generate sample data for testing |

## Schema

```sql
CREATE TABLE messages (
    id VARCHAR PRIMARY KEY,        -- Message ID from email headers
    message_id VARCHAR,            -- Full Message-ID header
    subject VARCHAR,               -- Email subject
    author VARCHAR,                -- From header (name + email)
    date TIMESTAMP,                -- Parsed date
    content TEXT,                  -- Full message body
    url VARCHAR,                   -- Archive URL
    thread_id VARCHAR,             -- Thread grouping ID
    list_name VARCHAR,             -- Mailing list (e.g., 'pgsql-hackers')
    crawled_at TIMESTAMP           -- When we scraped it
);
```

## Sample Data

The included `postgres_mailing_lists.duckdb` contains 8 realistic sample messages from pgsql-hackers covering:

- Incremental materialized view proposals (Tom Lane, Andres Freund)
- Hash join performance patches (David Rowley, Robert Haas)
- JSON path improvements RFC (Alvaro Herrera)
- Parallel query regression fixes (Amit Kapila, Thomas Munro)
- Commitfest status updates (Michael Paquier)

## Data Source

- **URL**: https://www.postgresql.org/list/pgsql-hackers/
- **License**: PostgreSQL License (permissive)
- **Update Frequency**: Daily (planned)

## TODO

- [ ] Test `scrape_to_duckdb.py` on unrestricted network
- [ ] Add pagination support to scrape historical archives
- [ ] Parse email threading (In-Reply-To headers)
- [ ] Extract structured metadata (patch attachments, commit refs)
- [ ] Add chunking logic for embedding preparation
- [ ] Generate embeddings with text-embedding-3-small
- [ ] Export to Parquet for Vector Bucket upload
- [ ] Add other lists: pgsql-general, pgsql-performance, pgsql-announce
- [ ] Set up scheduled crawl job

## Running the Scraper

```bash
cd datasets/postgres-mailing-lists
uv run --with requests --with beautifulsoup4 --with duckdb scrape_to_duckdb.py

# Check results
uv run --with duckdb python -c "import duckdb; print(duckdb.connect('postgres_mailing_lists.duckdb').execute('SELECT COUNT(*) FROM messages').fetchone())"
```

## Query Examples

```sql
-- Recent messages
SELECT subject, author, date
FROM messages
ORDER BY date DESC
LIMIT 10;

-- Messages by thread
SELECT thread_id, COUNT(*) as msg_count, MIN(date) as started
FROM messages
GROUP BY thread_id
ORDER BY started DESC;

-- Search content
SELECT subject, author, date
FROM messages
WHERE content ILIKE '%performance%'
ORDER BY date DESC;

-- Top contributors
SELECT
    split_part(author, '<', 1) as name,
    COUNT(*) as messages
FROM messages
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10;
```

## Next Steps

Once the scraper is tested and we have real data:

1. **Chunk** messages into ~1000 char segments with overlap
2. **Embed** using OpenAI text-embedding-3-small (1536 dims)
3. **Export** to Parquet format
4. **Upload** to Vector Bucket at `s3://vector-bucket/postgres-mailing-lists/v{date}/`
5. **Register** in dataset registry

## License

- **Data**: PostgreSQL License (from postgresql.org archives)
- **Code**: Apache-2.0
