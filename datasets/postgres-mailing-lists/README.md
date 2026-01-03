# PostgreSQL Mailing Lists Dataset

Pre-crawled PostgreSQL mailing list archives for RAG applications.

## Status

🚧 **In Progress** — Scraper ready, Iceberg integration complete.

## Quick Start

```bash
cd datasets/postgres-mailing-lists

# 1. Scrape to local DuckDB (for testing)
uv run --with requests --with beautifulsoup4 --with duckdb 01_scrape_local.py

# 2. View local data
uv run --with duckdb python -c "
import duckdb
conn = duckdb.connect('data/messages.duckdb')
print(conn.execute('SELECT subject, author FROM messages LIMIT 5').fetchall())
"
```

## Scripts

| Script | Description |
|--------|-------------|
| `01_scrape_local.py` | Scrape to local DuckDB for verification |
| `02_setup_iceberg.py` | Create namespace/table in Supabase Iceberg |
| `03_scrape_iceberg.py` | Scrape directly to remote Iceberg bucket |

## Workflow

### Step 1: Local Testing

Scrape a few messages to local DuckDB to verify everything works:

```bash
uv run --with requests --with beautifulsoup4 --with duckdb 01_scrape_local.py
```

Output: `./data/messages.duckdb`

### Step 2: Configure Supabase

Copy the environment template and add your Supabase credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
TOKEN=your_token
WAREHOUSE=your_warehouse
S3_ENDPOINT=https://xxx.supabase.co/storage/v1/s3
CATALOG_URI=https://xxx.supabase.co/storage/v1/iceberg
```

### Step 3: Setup Iceberg

Create the namespace and table in Supabase:

```bash
uv run --with pyiceberg --with python-dotenv 02_setup_iceberg.py
```

This creates:
- Namespace: `postgres_mailing_lists`
- Table: `postgres_mailing_lists.messages`

### Step 4: Scrape to Iceberg

Scrape messages directly to the remote Iceberg bucket:

```bash
# Scrape 10 messages (default)
uv run --with pyiceberg --with python-dotenv --with requests --with beautifulsoup4 03_scrape_iceberg.py

# Scrape more messages
uv run --with pyiceberg --with python-dotenv --with requests --with beautifulsoup4 03_scrape_iceberg.py --limit 50
```

## Schema

```sql
CREATE TABLE messages (
    id VARCHAR PRIMARY KEY,        -- Message ID from URL
    message_id VARCHAR,            -- Full Message-ID header
    subject VARCHAR,               -- Email subject
    author VARCHAR,                -- From header
    date VARCHAR,                  -- Date string
    date_parsed TIMESTAMP,         -- Parsed timestamp
    content TEXT,                  -- Full message body
    url VARCHAR,                   -- Archive URL
    thread_id VARCHAR,             -- Thread grouping ID
    list_name VARCHAR,             -- Mailing list name
    crawled_at TIMESTAMP           -- Scrape timestamp
);
```

## Data Source

- **URL**: https://www.postgresql.org/list/pgsql-hackers/
- **License**: PostgreSQL License (permissive)
- **Lists**: pgsql-hackers (more planned)

## TODO

- [ ] Add pagination to scrape historical archives
- [ ] Parse email threading (In-Reply-To headers)
- [ ] Extract structured metadata (patch attachments, commit refs)
- [ ] Add chunking logic for embedding preparation
- [ ] Generate embeddings with text-embedding-3-small
- [ ] Add other lists: pgsql-general, pgsql-performance, pgsql-announce
- [ ] Set up scheduled crawl job (GitHub Actions)

## Query Examples

Once data is in Iceberg, query via any Iceberg-compatible tool:

```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog("supabase", ...)
table = catalog.load_table("postgres_mailing_lists.messages")

# Read all data
df = table.scan().to_pandas()

# Filter by author
df = table.scan(
    row_filter="author LIKE '%Tom Lane%'"
).to_pandas()
```

## Files

```
├── .env.example           # Environment template (copy to .env)
├── 01_scrape_local.py     # Local DuckDB scraper
├── 02_setup_iceberg.py    # Iceberg namespace/table setup
├── 03_scrape_iceberg.py   # Remote Iceberg scraper
├── data/                  # Local data directory
│   └── messages.duckdb    # Local DuckDB database
└── README.md
```

## License

- **Data**: PostgreSQL License (from postgresql.org archives)
- **Code**: Apache-2.0
