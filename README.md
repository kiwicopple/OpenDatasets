# Supabase Open Datasets

Public, versioned embedding datasets for RAG applications — stored in Supabase Analytics Buckets and Vector Buckets.

## Status

🚧 **In Development** — Core tooling ready, first dataset in progress.

## Overview

This repository provides:
1. **Tooling** (`src/opendatasets`) — Python modules for scraping, chunking, embedding, and uploading to Supabase
2. **Datasets** (`datasets/`) — Pre-built embedding datasets ready for RAG

## Quick Start

```bash
# Clone and install
git clone https://github.com/supabase/OpenDatasets
cd OpenDatasets
uv sync

# Run example
uv run python -c "
from opendatasets import Scraper, Chunker
scraper = Scraper(base_url='https://example.com')
chunker = Chunker(chunk_size=1000, overlap=200)
"
```

## Project Structure

```
├── pyproject.toml              # uv project configuration
├── src/opendatasets/           # Core Python package
│   ├── scraper.py              # Web scraping utilities
│   ├── chunker.py              # Text chunking + OpenAI embeddings
│   ├── iceberg.py              # Supabase Analytics Buckets (PyIceberg)
│   └── vector.py               # Supabase Vector Buckets (S3/Parquet)
├── datasets/                   # Individual datasets
│   ├── postgres-mailing-lists/ # PostgreSQL mailing list archives
│   └── hackernews/             # Hacker News stories and discussions
└── SPEC.md                     # Technical specification
```

## Core Modules

| Module | Purpose |
|--------|---------|
| `scraper` | Rate-limited web crawling with BeautifulSoup |
| `chunker` | Fixed/sentence chunking, OpenAI embeddings |
| `iceberg` | PyIceberg client for Supabase Analytics Buckets |
| `vector` | S3 client for Supabase Vector Buckets |

### Example: Scrape → Chunk → Embed → Upload

```python
from opendatasets import Scraper, Chunker, embed_chunks, VectorClient
from opendatasets.vector import create_embeddings_table

# 1. Scrape
scraper = Scraper(base_url="https://docs.example.com")
pages = list(scraper.crawl("/", max_pages=100))

# 2. Chunk
chunker = Chunker(chunk_size=1000, overlap=200)
chunks = []
for page in pages:
    chunks.extend(chunker.chunk(doc_id=page.url, text=page.content))

# 3. Embed
chunks_with_embeddings = embed_chunks(chunks)

# 4. Upload to Vector Bucket
client = VectorClient()
table = create_embeddings_table(
    chunks=[c.model_dump() for c in chunks_with_embeddings],
    embeddings=[c.embedding for c in chunks_with_embeddings],
)
client.write_embeddings("my-dataset", "v1.0.0", table)
```

## Datasets

### Available

| Dataset | Description | Status |
|---------|-------------|--------|
| [`postgres-mailing-lists`](./datasets/postgres-mailing-lists/) | PostgreSQL mailing list archives (pgsql-hackers) | 🚧 In Progress |
| [`hackernews`](./datasets/hackernews/) | Hacker News stories and discussions | 🚧 In Progress |

### Planned

| Dataset | Description | Source |
|---------|-------------|--------|
| `oss-docs` | OSS documentation (React, Vue, Next.js, etc.) | Web crawl |
| `arxiv-abstracts` | arXiv paper abstracts | API |
| `rfc-repository` | IETF RFCs, Rust RFCs, Python PEPs | Web crawl |

## Configuration

Set environment variables for Supabase access:

```bash
# Supabase Storage
export SUPABASE_S3_ENDPOINT="https://<project>.supabase.co/storage/v1/s3"
export SUPABASE_ACCESS_KEY="your-access-key"
export SUPABASE_SECRET_KEY="your-secret-key"

# For Analytics Buckets (Iceberg)
export SUPABASE_ICEBERG_CATALOG_URI="https://<project>.supabase.co/storage/v1/iceberg"

# For embeddings
export OPENAI_API_KEY="your-openai-key"
```

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint
uv run ruff check src/
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web Sources   │────▶│   DuckDB ETL    │────▶│  Supabase S3    │
│   (Crawlers)    │     │   (Transform)   │     │  (Storage)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                              ┌──────────────────────────┤
                              ▼                          ▼
                    ┌─────────────────┐        ┌─────────────────┐
                    │   Analytics     │        │   Vector        │
                    │   Buckets       │        │   Buckets       │
                    │   (Iceberg)     │        │   (Parquet)     │
                    └─────────────────┘        └─────────────────┘
                              │                          │
                              └──────────────┬───────────┘
                                             ▼
                                   ┌─────────────────┐
                                   │ Edge Functions  │
                                   │ (Search API)    │
                                   └─────────────────┘
```

## License

- **Code**: Apache-2.0
- **Datasets**: Per-dataset licenses documented in each dataset's README

## Links

- [Technical Specification](./SPEC.md)
- [Supabase Analytics Buckets](https://supabase.com/docs/guides/storage/analytics/introduction)
- [PyIceberg Documentation](https://py.iceberg.apache.org/)
