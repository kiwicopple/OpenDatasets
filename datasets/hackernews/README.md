# Hacker News Dataset

Hacker News stories, comments, and metadata scraped from the official HN API.

## Data Source

- **API**: https://hacker-news.firebaseio.com/v0/
- **Documentation**: https://github.com/HackerNews/API
- **No API key required**

## Story Types

| Type | Description |
|------|-------------|
| `top` | Top stories on the front page |
| `new` | Newest stories |
| `best` | Best stories |
| `ask` | Ask HN posts |
| `show` | Show HN posts |
| `job` | Job postings |

## Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | int64 | Unique item ID |
| `type` | string | story, comment, job, poll, pollopt |
| `by` | string | Username of author |
| `time` | int64 | Unix timestamp |
| `time_parsed` | timestamp | Parsed timestamp |
| `title` | string | Story title |
| `url` | string | External URL (if any) |
| `text` | string | HTML content (for Ask HN, etc.) |
| `score` | int32 | Upvote score |
| `descendants` | int32 | Total comment count |
| `parent` | int64 | Parent item ID (for comments) |
| `story_type` | string | Type of story list (top, new, best, etc.) |
| `crawled_at` | timestamp | When the item was scraped |

## Workflow

### 1. Test Locally with DuckDB

```bash
cd datasets/hackernews

# Scrape top 10 stories to local DuckDB
uv run --with requests --with duckdb 01_scrape_local.py

# Scrape more stories
uv run --with requests --with duckdb 01_scrape_local.py --limit 50

# Scrape different story types
uv run --with requests --with duckdb 01_scrape_local.py --type best --limit 20
uv run --with requests --with duckdb 01_scrape_local.py --type ask --limit 20

# Data is stored in: ./data/hackernews.duckdb
```

### 2. Configure Supabase Credentials

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your Supabase credentials:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - TOKEN
# - WAREHOUSE
# - S3_ENDPOINT
# - CATALOG_URI
```

### 3. Create Iceberg Namespace and Table

```bash
uv run --with pyiceberg --with python-dotenv 02_setup_iceberg.py
```

This creates:
- Namespace: `hackernews`
- Table: `hackernews.items`

### 4. Scrape to Remote Iceberg

```bash
# Scrape top 10 stories
uv run --with pyiceberg --with python-dotenv --with requests 03_scrape_iceberg.py

# Scrape more stories
uv run --with pyiceberg --with python-dotenv --with requests 03_scrape_iceberg.py --limit 100

# Scrape best stories
uv run --with pyiceberg --with python-dotenv --with requests 03_scrape_iceberg.py --type best --limit 50
```

## Query Examples

### Local DuckDB

```python
import duckdb

conn = duckdb.connect("data/hackernews.duckdb")

# Top scored stories
conn.execute("""
    SELECT title, score, by, url
    FROM items
    WHERE type = 'story'
    ORDER BY score DESC
    LIMIT 10
""").fetchall()

# Stories by domain
conn.execute("""
    SELECT
        regexp_extract(url, 'https?://([^/]+)', 1) as domain,
        COUNT(*) as count
    FROM items
    WHERE url IS NOT NULL
    GROUP BY domain
    ORDER BY count DESC
    LIMIT 10
""").fetchall()
```

### Remote Iceberg (via DuckDB)

```python
import duckdb

conn = duckdb.connect()
conn.execute("INSTALL iceberg; LOAD iceberg;")

# Query the remote table
conn.execute("""
    SELECT title, score, by
    FROM iceberg_scan('s3://your-bucket/hackernews/items')
    ORDER BY score DESC
    LIMIT 10
""").fetchall()
```

## Rate Limiting

The HN API has no official rate limit, but the scripts include a 100ms delay between requests to be respectful. For bulk scraping, consider:

- Running during off-peak hours
- Increasing the delay between requests
- Caching responses locally

## TODOs

- [ ] Add comment scraping (traverse `kids` arrays)
- [ ] Add incremental scraping (only fetch new items)
- [ ] Add chunking and embedding pipeline
- [ ] Create Edge Function for semantic search
