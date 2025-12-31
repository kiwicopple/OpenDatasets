# Public Embedding Datasets — Technical Specification

**Version:** 0.1.0
**Status:** Draft
**Authors:** Supabase Platform Team
**Last Updated:** 2024-12-31

---

## Table of Contents

1. [Overview](#overview)
2. [Goals and Non-Goals](#goals-and-non-goals)
3. [Architecture](#architecture)
4. [Dataset Registry](#dataset-registry)
5. [Data Pipeline](#data-pipeline)
6. [DuckDB Integration](#duckdb-integration)
7. [Analytics Buckets](#analytics-buckets)
8. [Vector Buckets](#vector-buckets)
9. [Access Patterns](#access-patterns)
10. [Partner Integrations](#partner-integrations)
11. [Governance](#governance)
12. [Operational Considerations](#operational-considerations)

---

## Overview

Public Embedding Datasets provides pre-processed, versioned embedding datasets hosted in Supabase's Vector Buckets. The system enables instant RAG capabilities without requiring users to build data pipelines for crawling, chunking, or embedding.

### Prior Art

- **BigQuery Public Datasets** — Google's curated collection of public datasets
- **Hugging Face Datasets** — ML-focused dataset repository
- **Common Crawl** — Web archive corpus

---

## Goals and Non-Goals

### Goals

- Ship public, versioned embedding datasets
- Enable SQL-native querying via pgvector
- Provide REST API access via PostgREST
- Support reproducible retrieval with immutable versions
- Enable sponsorship model for dataset ingestion

### Non-Goals

- Training ML models
- Real-time write APIs (read-only initially)
- User-generated dataset uploads (curated only)
- Custom embedding model support (standardized models only)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  Firecrawl   │    │  Protomaps   │    │   Custom     │                  │
│  │  (Web/Docs)  │    │  (Geo Data)  │    │  Ingestion   │                  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
│         │                   │                   │                          │
│         └───────────────────┼───────────────────┘                          │
│                             ▼                                              │
│                  ┌─────────────────────┐                                   │
│                  │   DuckDB Pipeline   │                                   │
│                  │   (ETL Processor)   │                                   │
│                  └──────────┬──────────┘                                   │
│                             │                                              │
└─────────────────────────────┼──────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼──────────────────────────────────────────────┐
│                             ▼            STORAGE LAYER                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────┐    ┌────────────────────────────┐          │
│  │     Analytics Buckets      │    │      Vector Buckets        │          │
│  │                            │    │                            │          │
│  │  • Raw crawl data          │    │  • Embedding vectors       │          │
│  │  • Metadata/attribution    │    │  • Chunk content           │          │
│  │  • Version snapshots       │    │  • HNSW/IVFFLAT indexes    │          │
│  │  • Parquet format          │    │  • Similarity search       │          │
│  │                            │    │                            │          │
│  └────────────────────────────┘    └────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼──────────────────────────────────────────────┐
│                             ▼            ACCESS LAYER                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │     SQL      │    │  PostgREST   │    │    Edge      │                  │
│  │  (pgvector)  │    │    (REST)    │    │  Functions   │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Dataset Registry

### Schema

```sql
CREATE SCHEMA IF NOT EXISTS datasets;

-- Core registry table
CREATE TABLE datasets.registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,

    -- Versioning
    current_version TEXT NOT NULL,
    versions JSONB NOT NULL DEFAULT '[]',

    -- Technical metadata
    record_count BIGINT,
    chunk_count BIGINT,
    embedding_model TEXT NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    chunk_strategy TEXT, -- 'fixed', 'semantic', 'document'

    -- Licensing
    spdx_license TEXT NOT NULL,
    license_url TEXT,
    attribution_required BOOLEAN DEFAULT false,

    -- Sponsorship
    sponsor_name TEXT,
    sponsor_url TEXT,
    sponsor_logo_url TEXT,

    -- Storage locations
    analytics_bucket_path TEXT,
    vector_bucket_path TEXT,

    -- Checksums
    checksum_sha256 TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_synced_at TIMESTAMPTZ
);

-- Version history
CREATE TABLE datasets.versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES datasets.registry(id),
    version TEXT NOT NULL,

    -- Snapshot metadata
    record_count BIGINT,
    chunk_count BIGINT,
    checksum_sha256 TEXT NOT NULL,

    -- Storage
    analytics_snapshot_path TEXT,
    vector_snapshot_path TEXT,

    -- Changelog
    changelog TEXT,
    breaking_changes BOOLEAN DEFAULT false,

    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE(dataset_id, version)
);

-- Per-record attribution (for mixed-license datasets)
CREATE TABLE datasets.attributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES datasets.registry(id),
    record_id TEXT NOT NULL,

    source_url TEXT,
    author TEXT,
    license TEXT,
    attribution_text TEXT,

    created_at TIMESTAMPTZ DEFAULT now()
);

-- Access tracking
CREATE TABLE datasets.access_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES datasets.registry(id),
    project_id UUID,

    access_type TEXT, -- 'link', 'query', 'rest'
    query_count INTEGER DEFAULT 1,

    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Registry Functions

```sql
-- Link a dataset to a project
CREATE OR REPLACE FUNCTION supabase.link_dataset(
    dataset_name TEXT,
    version TEXT DEFAULT 'latest'
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_dataset RECORD;
    v_version TEXT;
    v_schema_name TEXT;
BEGIN
    -- Resolve dataset
    SELECT * INTO v_dataset
    FROM datasets.registry
    WHERE name = dataset_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dataset not found: %', dataset_name;
    END IF;

    -- Resolve version
    IF version = 'latest' THEN
        v_version := v_dataset.current_version;
    ELSE
        v_version := version;
    END IF;

    -- Create schema for dataset
    v_schema_name := replace(dataset_name, '-', '_');
    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', v_schema_name);

    -- Create foreign tables pointing to vector bucket
    EXECUTE format($q$
        CREATE FOREIGN TABLE IF NOT EXISTS %I.chunks (
            id UUID,
            content TEXT,
            embedding vector(%s),
            metadata JSONB,
            source_url TEXT,
            chunk_index INTEGER,
            created_at TIMESTAMPTZ
        ) SERVER vector_bucket_server
        OPTIONS (
            bucket_path '%s',
            version '%s'
        )
    $q$,
        v_schema_name,
        v_dataset.embedding_dimensions,
        v_dataset.vector_bucket_path,
        v_version
    );

    -- Log access
    INSERT INTO datasets.access_log (dataset_id, access_type)
    VALUES (v_dataset.id, 'link');
END;
$$;

-- List available versions
CREATE OR REPLACE FUNCTION supabase.dataset_versions(dataset_name TEXT)
RETURNS TABLE (
    version TEXT,
    record_count BIGINT,
    created_at TIMESTAMPTZ,
    changelog TEXT
)
LANGUAGE sql
AS $$
    SELECT v.version, v.record_count, v.created_at, v.changelog
    FROM datasets.versions v
    JOIN datasets.registry r ON r.id = v.dataset_id
    WHERE r.name = dataset_name
    ORDER BY v.created_at DESC;
$$;

-- Get dataset metadata
CREATE OR REPLACE FUNCTION supabase.dataset_metadata(dataset_name TEXT)
RETURNS TABLE (
    version TEXT,
    record_count BIGINT,
    embedding_model TEXT,
    checksum TEXT,
    created_at TIMESTAMPTZ,
    sponsor TEXT
)
LANGUAGE sql
AS $$
    SELECT
        current_version,
        record_count,
        embedding_model,
        checksum_sha256,
        updated_at,
        sponsor_name
    FROM datasets.registry
    WHERE name = dataset_name;
$$;
```

---

## Data Pipeline

### Pipeline Stages

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Crawl   │───▶│  Clean   │───▶│  Chunk   │───▶│  Embed   │───▶│  Index   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
  Raw HTML      Markdown/Text    Chunks JSON    Vectors Parquet   HNSW Index
```

### Stage Definitions

| Stage | Input | Output | Tool |
|-------|-------|--------|------|
| Crawl | URLs/sitemaps | Raw HTML/JSON | Firecrawl |
| Clean | Raw content | Markdown/Text | Custom processors |
| Chunk | Clean text | Chunk records | LangChain/Custom |
| Embed | Chunks | Vector arrays | OpenAI/Voyage |
| Index | Vectors | HNSW/IVFFLAT | pgvector |

---

## DuckDB Integration

DuckDB serves as the primary ETL processor for transforming crawled data into Analytics Buckets and Vector Buckets format.

### Installation & Setup

```bash
# Install DuckDB with required extensions
pip install duckdb

# Or use the CLI
brew install duckdb
```

### DuckDB Configuration

```sql
-- Load required extensions
INSTALL httpfs;
INSTALL parquet;
INSTALL json;

LOAD httpfs;
LOAD parquet;
LOAD json;

-- Configure S3-compatible storage (Supabase Storage)
SET s3_region = 'auto';
SET s3_endpoint = 'YOUR_PROJECT.supabase.co/storage/v1/s3';
SET s3_access_key_id = 'YOUR_ACCESS_KEY';
SET s3_secret_access_key = 'YOUR_SECRET_KEY';
SET s3_url_style = 'path';
```

### Pipeline: Raw Crawl to Analytics Bucket

```sql
-- Step 1: Ingest raw crawl data from Firecrawl
CREATE TABLE raw_crawl AS
SELECT * FROM read_json_auto('s3://firecrawl-output/oss-docs/*.json');

-- Step 2: Clean and normalize
CREATE TABLE cleaned_docs AS
SELECT
    md5(url) AS doc_id,
    url AS source_url,
    title,
    -- Clean markdown content
    regexp_replace(content, '<[^>]+>', '', 'g') AS clean_content,
    metadata,
    crawled_at,
    -- Extract license from metadata
    COALESCE(metadata->>'license', 'unknown') AS license
FROM raw_crawl
WHERE content IS NOT NULL
  AND length(content) > 100;

-- Step 3: Export to Analytics Bucket (Parquet format)
COPY cleaned_docs TO 's3://analytics-bucket/oss-docs/v2024.12.1/docs.parquet'
(FORMAT PARQUET, COMPRESSION 'zstd');

-- Step 4: Create metadata sidecar
COPY (
    SELECT
        'oss-docs' AS dataset_name,
        'v2024.12.1' AS version,
        count(*) AS record_count,
        current_timestamp AS created_at,
        'firecrawl' AS source,
        'MIT/Apache' AS license
    FROM cleaned_docs
) TO 's3://analytics-bucket/oss-docs/v2024.12.1/metadata.json'
(FORMAT JSON);
```

### Pipeline: Chunking with DuckDB

```sql
-- Create chunking UDF (using DuckDB's Python integration)
CREATE OR REPLACE FUNCTION chunk_text(content VARCHAR, chunk_size INT, overlap INT)
RETURNS TABLE(chunk_index INT, chunk_content VARCHAR)
LANGUAGE PYTHON
AS $$
    chunks = []
    text = content
    idx = 0
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append((idx, text[start:end]))
        start = end - overlap
        idx += 1
    return chunks
$$;

-- Apply chunking
CREATE TABLE chunks AS
SELECT
    doc_id,
    source_url,
    chunk.chunk_index,
    chunk.chunk_content,
    license
FROM cleaned_docs,
LATERAL chunk_text(clean_content, 1000, 200) AS chunk;

-- Export chunks for embedding
COPY chunks TO 's3://analytics-bucket/oss-docs/v2024.12.1/chunks.parquet'
(FORMAT PARQUET, COMPRESSION 'zstd');
```

### Pipeline: Embedding Integration

```python
#!/usr/bin/env python3
"""
DuckDB + OpenAI Embedding Pipeline

Processes chunks from Analytics Bucket and writes to Vector Bucket.
"""

import duckdb
import openai
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import pyarrow as pa
import pyarrow.parquet as pq

# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 100
MAX_WORKERS = 10

# Initialize clients
db = duckdb.connect()
client = openai.OpenAI()

# Configure DuckDB for S3
db.execute("""
    SET s3_endpoint = 'YOUR_PROJECT.supabase.co/storage/v1/s3';
    SET s3_access_key_id = 'YOUR_ACCESS_KEY';
    SET s3_secret_access_key = 'YOUR_SECRET_KEY';
""")

def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using OpenAI."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMENSIONS
    )
    return [e.embedding for e in response.data]

def process_chunks():
    """Process all chunks and generate embeddings."""

    # Load chunks from Analytics Bucket
    chunks_df = db.execute("""
        SELECT doc_id, source_url, chunk_index, chunk_content, license
        FROM read_parquet('s3://analytics-bucket/oss-docs/v2024.12.1/chunks.parquet')
    """).fetchdf()

    # Process in batches
    embeddings = []
    for i in range(0, len(chunks_df), BATCH_SIZE):
        batch = chunks_df.iloc[i:i+BATCH_SIZE]
        batch_embeddings = embed_batch(batch['chunk_content'].tolist())
        embeddings.extend(batch_embeddings)
        print(f"Processed {min(i+BATCH_SIZE, len(chunks_df))}/{len(chunks_df)} chunks")

    # Add embeddings to dataframe
    chunks_df['embedding'] = embeddings

    # Convert to Arrow format with vector type
    schema = pa.schema([
        ('doc_id', pa.string()),
        ('source_url', pa.string()),
        ('chunk_index', pa.int32()),
        ('chunk_content', pa.string()),
        ('license', pa.string()),
        ('embedding', pa.list_(pa.float32(), EMBEDDING_DIMENSIONS))
    ])

    table = pa.Table.from_pandas(chunks_df, schema=schema)

    # Write to Vector Bucket
    pq.write_table(
        table,
        's3://vector-bucket/oss-docs/v2024.12.1/embeddings.parquet',
        compression='zstd'
    )

    print(f"Wrote {len(chunks_df)} embeddings to Vector Bucket")

if __name__ == "__main__":
    process_chunks()
```

### Full DuckDB Pipeline Script

```sql
-- ============================================================================
-- COMPLETE DUCKDB PIPELINE: Crawl → Analytics Bucket → Vector Bucket
-- ============================================================================

-- Configuration
SET VARIABLE dataset_name = 'oss-docs';
SET VARIABLE dataset_version = 'v2024.12.1';
SET VARIABLE chunk_size = 1000;
SET VARIABLE chunk_overlap = 200;

-- Step 1: Load raw crawl data
CREATE OR REPLACE TABLE raw_crawl AS
SELECT * FROM read_json_auto(
    's3://firecrawl-output/' || getvariable('dataset_name') || '/*.json'
);

-- Step 2: Clean and deduplicate
CREATE OR REPLACE TABLE cleaned AS
SELECT DISTINCT ON (url)
    gen_random_uuid()::VARCHAR AS id,
    url AS source_url,
    title,
    regexp_replace(content, '<[^>]+>', '', 'g') AS content,
    metadata,
    COALESCE(metadata->>'license', 'MIT') AS license,
    COALESCE(metadata->>'author', 'Unknown') AS author,
    now() AS processed_at
FROM raw_crawl
WHERE content IS NOT NULL
  AND length(content) > 50
ORDER BY url, crawled_at DESC;

-- Step 3: Create chunks table with windowed chunking
CREATE OR REPLACE TABLE chunks AS
WITH RECURSIVE chunk_recursive AS (
    -- Base case: first chunk
    SELECT
        id AS doc_id,
        source_url,
        title,
        license,
        author,
        0 AS chunk_index,
        substr(content, 1, getvariable('chunk_size')) AS chunk_content,
        content,
        length(content) AS total_length
    FROM cleaned

    UNION ALL

    -- Recursive case: subsequent chunks
    SELECT
        doc_id,
        source_url,
        title,
        license,
        author,
        chunk_index + 1,
        substr(
            content,
            (chunk_index + 1) * (getvariable('chunk_size') - getvariable('chunk_overlap')) + 1,
            getvariable('chunk_size')
        ),
        content,
        total_length
    FROM chunk_recursive
    WHERE (chunk_index + 1) * (getvariable('chunk_size') - getvariable('chunk_overlap')) < total_length
)
SELECT
    gen_random_uuid()::VARCHAR AS chunk_id,
    doc_id,
    source_url,
    title,
    license,
    author,
    chunk_index,
    chunk_content,
    length(chunk_content) AS chunk_length
FROM chunk_recursive
WHERE length(chunk_content) > 50;

-- Step 4: Export to Analytics Bucket
COPY cleaned TO
    's3://analytics-bucket/' || getvariable('dataset_name') || '/' ||
    getvariable('dataset_version') || '/documents.parquet'
(FORMAT PARQUET, COMPRESSION 'zstd');

COPY chunks TO
    's3://analytics-bucket/' || getvariable('dataset_name') || '/' ||
    getvariable('dataset_version') || '/chunks.parquet'
(FORMAT PARQUET, COMPRESSION 'zstd');

-- Step 5: Generate manifest
COPY (
    SELECT
        getvariable('dataset_name') AS dataset,
        getvariable('dataset_version') AS version,
        (SELECT count(*) FROM cleaned) AS document_count,
        (SELECT count(*) FROM chunks) AS chunk_count,
        getvariable('chunk_size') AS chunk_size,
        getvariable('chunk_overlap') AS chunk_overlap,
        now() AS created_at,
        md5(
            (SELECT string_agg(chunk_content, '') FROM chunks ORDER BY chunk_id)
        ) AS content_checksum
) TO 's3://analytics-bucket/' || getvariable('dataset_name') || '/' ||
     getvariable('dataset_version') || '/manifest.json'
(FORMAT JSON);

-- Summary
SELECT
    'Pipeline Complete' AS status,
    (SELECT count(*) FROM cleaned) AS documents,
    (SELECT count(*) FROM chunks) AS chunks,
    getvariable('dataset_name') AS dataset,
    getvariable('dataset_version') AS version;
```

---

## Analytics Buckets

Analytics Buckets store the raw and processed data in columnar format (Parquet) for efficient analytical queries.

### Bucket Structure

```
analytics-bucket/
├── {dataset-name}/
│   ├── {version}/
│   │   ├── documents.parquet      # Full documents
│   │   ├── chunks.parquet         # Chunked content
│   │   ├── manifest.json          # Version metadata
│   │   └── attributions.parquet   # Per-record licensing
│   └── latest -> v2024.12.1/      # Symlink to current
└── _registry/
    └── datasets.parquet           # Global registry
```

### Parquet Schema: Documents

```
message Document {
    required binary id (STRING);
    required binary source_url (STRING);
    optional binary title (STRING);
    required binary content (STRING);
    optional binary metadata (JSON);
    required binary license (STRING);
    optional binary author (STRING);
    required int64 processed_at (TIMESTAMP_MILLIS);
}
```

### Parquet Schema: Chunks

```
message Chunk {
    required binary chunk_id (STRING);
    required binary doc_id (STRING);
    required binary source_url (STRING);
    optional binary title (STRING);
    required binary license (STRING);
    required int32 chunk_index;
    required binary chunk_content (STRING);
    required int32 chunk_length;
}
```

### Querying Analytics Buckets via DuckDB

```sql
-- Direct query from Analytics Bucket
SELECT
    title,
    source_url,
    length(content) AS content_length,
    license
FROM read_parquet('s3://analytics-bucket/oss-docs/v2024.12.1/documents.parquet')
WHERE license = 'MIT'
ORDER BY content_length DESC
LIMIT 10;

-- Aggregation across versions
SELECT
    split_part(filename, '/', 3) AS version,
    count(*) AS chunk_count,
    avg(chunk_length) AS avg_chunk_size
FROM read_parquet('s3://analytics-bucket/oss-docs/*/chunks.parquet', filename=true)
GROUP BY 1
ORDER BY 1 DESC;
```

---

## Vector Buckets

Vector Buckets store embedding vectors alongside chunk content, optimized for similarity search.

### Bucket Structure

```
vector-bucket/
├── {dataset-name}/
│   ├── {version}/
│   │   ├── embeddings.parquet     # Vectors + content
│   │   ├── index.hnsw             # HNSW index file
│   │   └── manifest.json          # Index metadata
│   └── latest -> v2024.12.1/
└── _indexes/
    └── hot/                       # Frequently accessed indexes
        └── {dataset-name}.hnsw
```

### Parquet Schema: Embeddings

```
message Embedding {
    required binary chunk_id (STRING);
    required binary doc_id (STRING);
    required binary source_url (STRING);
    required binary chunk_content (STRING);
    required binary license (STRING);
    required int32 chunk_index;
    required fixed_len_byte_array(6144) embedding;  # 1536 x float32
    optional binary metadata (JSON);
}
```

### Loading into pgvector

```sql
-- Create the target table
CREATE TABLE oss_docs.chunks (
    chunk_id UUID PRIMARY KEY,
    doc_id UUID,
    source_url TEXT,
    chunk_content TEXT,
    license TEXT,
    chunk_index INTEGER,
    embedding vector(1536),
    metadata JSONB,

    -- Indexing
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Create HNSW index for fast similarity search
CREATE INDEX ON oss_docs.chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Load from Vector Bucket using postgres_fdw + parquet_fdw
CREATE EXTENSION IF NOT EXISTS parquet_fdw;

CREATE SERVER vector_bucket_server
FOREIGN DATA WRAPPER parquet_fdw;

CREATE FOREIGN TABLE oss_docs.chunks_external (
    chunk_id TEXT,
    doc_id TEXT,
    source_url TEXT,
    chunk_content TEXT,
    license TEXT,
    chunk_index INTEGER,
    embedding REAL[]
)
SERVER vector_bucket_server
OPTIONS (
    filename 's3://vector-bucket/oss-docs/v2024.12.1/embeddings.parquet'
);

-- Materialize into local table
INSERT INTO oss_docs.chunks (
    chunk_id, doc_id, source_url, chunk_content,
    license, chunk_index, embedding
)
SELECT
    chunk_id::UUID,
    doc_id::UUID,
    source_url,
    chunk_content,
    license,
    chunk_index,
    embedding::vector(1536)
FROM oss_docs.chunks_external;
```

### Similarity Search

```sql
-- Function: Semantic search
CREATE OR REPLACE FUNCTION oss_docs.search(
    query_embedding vector(1536),
    match_count INT DEFAULT 10,
    filter_license TEXT DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    source_url TEXT,
    chunk_content TEXT,
    license TEXT,
    similarity FLOAT
)
LANGUAGE sql
AS $$
    SELECT
        chunk_id,
        source_url,
        chunk_content,
        license,
        1 - (embedding <=> query_embedding) AS similarity
    FROM oss_docs.chunks
    WHERE (filter_license IS NULL OR license = filter_license)
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
```

---

## Access Patterns

### SQL Access (pgvector)

```sql
-- Link dataset to project
SELECT supabase.link_dataset('oss-docs');

-- Semantic search
SELECT * FROM oss_docs.search(
    (SELECT embedding FROM embeddings WHERE id = 'query'),
    10
);

-- Full-text + vector hybrid search
SELECT
    c.chunk_content,
    c.source_url,
    1 - (c.embedding <=> query_embedding) AS vector_score,
    ts_rank(to_tsvector(c.chunk_content), query) AS text_score
FROM oss_docs.chunks c,
     plainto_tsquery('postgresql indexes') query,
     (SELECT embedding FROM embed('how do I create an index')) query_embedding
WHERE to_tsvector(c.chunk_content) @@ query
ORDER BY vector_score * 0.7 + text_score * 0.3 DESC
LIMIT 10;
```

### REST API Access

```bash
# Search endpoint
POST /datasets/v1/{dataset}/search
Content-Type: application/json

{
  "query": "how to create a table in PostgreSQL",
  "limit": 10,
  "filter": {
    "license": ["MIT", "Apache-2.0"]
  },
  "include_embeddings": false
}

# Response
{
  "results": [
    {
      "chunk_id": "abc123",
      "content": "To create a table in PostgreSQL...",
      "source_url": "https://postgresql.org/docs/...",
      "similarity": 0.89,
      "license": "PostgreSQL",
      "metadata": {...}
    }
  ],
  "usage": {
    "tokens": 150,
    "model": "text-embedding-3-small"
  }
}
```

### Edge Function Access

```typescript
// supabase/functions/rag-search/index.ts
import { createClient } from '@supabase/supabase-js'

Deno.serve(async (req) => {
  const { query, dataset = 'oss-docs', limit = 10 } = await req.json()

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  // Generate embedding
  const { data: embedding } = await supabase.functions.invoke('embed', {
    body: { text: query }
  })

  // Search dataset
  const { data: results } = await supabase
    .schema(dataset.replace('-', '_'))
    .rpc('search', {
      query_embedding: embedding,
      match_count: limit
    })

  return new Response(JSON.stringify({ results }), {
    headers: { 'Content-Type': 'application/json' }
  })
})
```

---

## Partner Integrations

### Firecrawl Integration

Firecrawl handles web crawling for documentation, code samples, and structured content.

```yaml
# firecrawl-config.yaml
datasets:
  - name: oss-docs
    sources:
      - url: https://react.dev/
        crawl_type: sitemap
        max_pages: 5000
      - url: https://vuejs.org/
        crawl_type: sitemap
        max_pages: 3000
      - url: https://nextjs.org/docs
        crawl_type: sitemap
        max_pages: 2000

    output:
      format: json
      destination: s3://firecrawl-output/oss-docs/

    schedule:
      cron: "0 0 * * 0"  # Weekly

    attribution:
      sponsor: Firecrawl
      sponsor_url: https://firecrawl.dev
```

```python
# firecrawl_pipeline.py
from firecrawl import FirecrawlApp
import duckdb

def crawl_and_ingest(config):
    """Firecrawl → DuckDB → Supabase Pipeline"""

    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

    for source in config['sources']:
        # Crawl
        results = app.crawl_url(
            source['url'],
            params={
                'crawlerOptions': {
                    'limit': source.get('max_pages', 1000)
                },
                'pageOptions': {
                    'includeMarkdown': True
                }
            }
        )

        # Write to staging
        with open(f"/tmp/{source['url'].replace('/', '_')}.json", 'w') as f:
            json.dump(results, f)

    # Process with DuckDB
    db = duckdb.connect()
    db.execute(open('pipeline.sql').read())
```

### Protomaps Integration

Protomaps provides geospatial data with pre-computed embeddings for location-based RAG.

```python
# protomaps_pipeline.py
import pmtiles
import duckdb
import openai

def process_protomaps_tiles(pmtiles_path: str, output_bucket: str):
    """Extract POIs from Protomaps and generate embeddings."""

    reader = pmtiles.Reader(open(pmtiles_path, 'rb'))
    db = duckdb.connect()

    # Create staging table
    db.execute("""
        CREATE TABLE pois (
            id VARCHAR,
            name VARCHAR,
            category VARCHAR,
            lat DOUBLE,
            lon DOUBLE,
            description VARCHAR,
            osm_id BIGINT
        )
    """)

    # Extract POIs from tiles
    for tile in reader.get_all_tiles():
        features = decode_mvt(tile.data)
        for feature in features:
            if feature.get('name'):
                db.execute("""
                    INSERT INTO pois VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    feature['id'],
                    feature['name'],
                    feature.get('category', 'unknown'),
                    feature['lat'],
                    feature['lon'],
                    f"{feature['name']} - {feature.get('category', '')} in {feature.get('city', 'unknown')}",
                    feature.get('osm_id')
                ])

    # Generate embeddings
    pois = db.execute("SELECT * FROM pois").fetchdf()
    embeddings = batch_embed(pois['description'].tolist())
    pois['embedding'] = embeddings

    # Export to Vector Bucket
    db.execute(f"""
        COPY (SELECT * FROM pois)
        TO '{output_bucket}/osm-places/v2024.12.1/embeddings.parquet'
        (FORMAT PARQUET)
    """)
```

---

## Governance

### Licensing

All datasets must have SPDX-compliant license identifiers:

| License | SPDX ID | Commercial Use | Attribution |
|---------|---------|----------------|-------------|
| MIT | MIT | Yes | Required |
| Apache 2.0 | Apache-2.0 | Yes | Required |
| Creative Commons Zero | CC0-1.0 | Yes | No |
| CC BY | CC-BY-4.0 | Yes | Required |
| CC BY-NC | CC-BY-NC-4.0 | No | Required |
| PostgreSQL | PostgreSQL | Yes | Required |
| ODbL | ODbL-1.0 | Yes | Required (share-alike) |

### Per-Record Attribution

For datasets with mixed licensing:

```sql
-- Query with attribution
SELECT
    c.chunk_content,
    c.source_url,
    a.license,
    a.attribution_text
FROM oss_docs.chunks c
LEFT JOIN datasets.attributions a ON c.chunk_id::text = a.record_id
WHERE c.chunk_id = 'some-id';
```

### Content Moderation

- All crawled content passes through content filters
- PII detection and removal
- Copyright claim handling process
- DMCA takedown compliance

---

## Operational Considerations

### Update Schedule

| Dataset | Update Frequency | Method |
|---------|------------------|--------|
| oss-docs | Weekly | Full recrawl |
| hacker-news | Daily | Incremental |
| arxiv-abstracts | Daily | API sync |
| postgres-mailing-lists | Daily | Incremental |
| regulations | Monthly | Differential |

### Storage Estimates

| Dataset | Documents | Chunks | Embeddings | Storage |
|---------|-----------|--------|------------|---------|
| oss-docs | 500K | 2M | 12GB | 15GB |
| hacker-news | 1M | 5M | 30GB | 40GB |
| arxiv-abstracts | 2.3M | 10M | 60GB | 75GB |

### Cost Model

```
Monthly Cost =
    Storage (GB) × $0.023/GB +
    Egress (GB) × $0.09/GB +
    Embedding API calls × $0.0001/1K tokens +
    Index maintenance × compute hours
```

### Monitoring

```sql
-- Dataset health check
SELECT
    r.name,
    r.current_version,
    r.record_count,
    r.last_synced_at,
    CASE
        WHEN r.last_synced_at < now() - interval '7 days' THEN 'stale'
        ELSE 'healthy'
    END AS status
FROM datasets.registry r
ORDER BY r.last_synced_at DESC;

-- Access patterns
SELECT
    r.name,
    date_trunc('day', a.created_at) AS day,
    count(*) AS queries,
    count(DISTINCT a.project_id) AS unique_projects
FROM datasets.access_log a
JOIN datasets.registry r ON r.id = a.dataset_id
WHERE a.created_at > now() - interval '30 days'
GROUP BY 1, 2
ORDER BY 1, 2;
```

---

## Appendix A: DuckDB Extension for Supabase

Future: Native DuckDB extension for Supabase Vector Buckets.

```sql
-- Proposed syntax
INSTALL supabase FROM community;
LOAD supabase;

-- Configure connection
CALL supabase_connect('https://project.supabase.co', 'service_role_key');

-- Query Vector Bucket directly
SELECT * FROM supabase_vector_search(
    bucket := 'oss-docs',
    query := 'how to create an index',
    limit := 10
);
```

---

## Appendix B: Dataset Proposal Template

```markdown
# Dataset Proposal: {Name}

## Overview
- **Description**:
- **Source**:
- **Update frequency**:
- **Estimated size**:

## Licensing
- **License**:
- **Attribution required**: Yes/No
- **Commercial use**: Yes/No

## Technical Details
- **Crawl method**:
- **Chunk strategy**:
- **Embedding model**:

## Sponsorship
- **Sponsor**:
- **Coverage**: Ingestion / Hosting / Both

## Checklist
- [ ] License verified
- [ ] Content moderation reviewed
- [ ] Storage estimate calculated
- [ ] Update pipeline designed
- [ ] Attribution requirements documented
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2024-12-31 | Platform Team | Initial draft |
