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
9. [Edge Functions](#edge-functions)
10. [REST API](#rest-api)
11. [Partner Integrations](#partner-integrations)
12. [Governance](#governance)
13. [Operational Considerations](#operational-considerations)

---

## Overview

Public Embedding Datasets provides pre-processed, versioned embedding datasets hosted in S3-compatible buckets. The system enables instant RAG capabilities without requiring users to build data pipelines for crawling, chunking, or embedding.

### Prior Art

- **BigQuery Public Datasets** — Google's curated collection of public datasets
- **Hugging Face Datasets** — ML-focused dataset repository
- **Common Crawl** — Web archive corpus

---

## Goals and Non-Goals

### Goals

- Ship public, versioned embedding datasets in S3 buckets
- Enable semantic search via Edge Functions
- Provide REST API access for search queries
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
│                             ▼            STORAGE LAYER (S3)                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────────────────┐    ┌────────────────────────────┐          │
│  │     Analytics Buckets      │    │      Vector Buckets        │          │
│  │         (S3)               │    │         (S3)               │          │
│  │                            │    │                            │          │
│  │  • Raw crawl data          │    │  • Embedding vectors       │          │
│  │  • Metadata/attribution    │    │  • Chunk content           │          │
│  │  • Version snapshots       │    │  • HNSW index files        │          │
│  │  • Parquet format          │    │  • Parquet format          │          │
│  │                            │    │                            │          │
│  └────────────────────────────┘    └────────────────────────────┘          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼──────────────────────────────────────────────┐
│                             ▼            ACCESS LAYER                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                    ┌──────────────────────┐                                │
│                    │    Edge Functions    │                                │
│                    │   (Search Service)   │                                │
│                    └──────────┬───────────┘                                │
│                               │                                            │
│              ┌────────────────┼────────────────┐                           │
│              ▼                ▼                ▼                           │
│       ┌──────────┐     ┌──────────┐     ┌──────────┐                      │
│       │  REST    │     │   SDK    │     │  DuckDB  │                      │
│       │   API    │     │  Client  │     │  Direct  │                      │
│       └──────────┘     └──────────┘     └──────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Dataset Registry

The dataset registry is stored as JSON files in S3, providing metadata about all available datasets.

### Registry Structure

```
s3://datasets-registry/
├── registry.json              # Master dataset list
├── datasets/
│   ├── oss-docs.json         # Per-dataset metadata
│   ├── hacker-news.json
│   └── arxiv-abstracts.json
└── sponsors/
    ├── firecrawl.json
    └── protomaps.json
```

### Registry Schema: registry.json

```json
{
  "version": "1.0.0",
  "updated_at": "2024-12-31T00:00:00Z",
  "datasets": [
    {
      "name": "oss-docs",
      "display_name": "OSS Documentation",
      "current_version": "v2024.12.1",
      "record_count": 2000000,
      "license": "MIT",
      "sponsor": "firecrawl"
    }
  ]
}
```

### Dataset Metadata Schema

```json
{
  "name": "oss-docs",
  "display_name": "OSS Documentation",
  "description": "Documentation from popular open source projects",

  "versioning": {
    "current": "v2024.12.1",
    "versions": [
      {
        "version": "v2024.12.1",
        "created_at": "2024-12-31T00:00:00Z",
        "record_count": 2000000,
        "chunk_count": 8500000,
        "checksum_sha256": "abc123...",
        "changelog": "Added Next.js 15 documentation"
      }
    ]
  },

  "technical": {
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1536,
    "chunk_strategy": "semantic",
    "chunk_size": 1000,
    "chunk_overlap": 200
  },

  "licensing": {
    "spdx_license": "MIT",
    "license_url": "https://opensource.org/licenses/MIT",
    "attribution_required": true
  },

  "sponsorship": {
    "sponsor_name": "Firecrawl",
    "sponsor_url": "https://firecrawl.dev",
    "sponsor_logo_url": "https://firecrawl.dev/logo.svg"
  },

  "storage": {
    "analytics_bucket": "s3://analytics-bucket/oss-docs/",
    "vector_bucket": "s3://vector-bucket/oss-docs/"
  }
}
```

### Attributions Schema

Per-record attribution for mixed-license datasets, stored as Parquet:

```
s3://analytics-bucket/{dataset}/attributions.parquet
```

| Column | Type | Description |
|--------|------|-------------|
| record_id | STRING | Unique chunk/document ID |
| source_url | STRING | Original source URL |
| author | STRING | Content author |
| license | STRING | SPDX license identifier |
| attribution_text | STRING | Required attribution text |

---

## Data Pipeline

### Pipeline Stages

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Crawl   │───▶│  Clean   │───▶│  Chunk   │───▶│  Embed   │───▶│  Upload  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     ▼               ▼               ▼               ▼               ▼
  Raw HTML      Markdown/Text    Chunks JSON    Parquet+Vectors   S3 Buckets
```

### Stage Definitions

| Stage | Input | Output | Tool |
|-------|-------|--------|------|
| Crawl | URLs/sitemaps | Raw HTML/JSON | Firecrawl |
| Clean | Raw content | Markdown/Text | Custom processors |
| Chunk | Clean text | Chunk records | LangChain/Custom |
| Embed | Chunks | Vector arrays | OpenAI/Voyage |
| Upload | Parquet files | S3 objects | DuckDB/AWS CLI |

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
import pyarrow as pa
import pyarrow.parquet as pq

# Configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 100

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
s3://analytics-bucket/
├── {dataset-name}/
│   ├── {version}/
│   │   ├── documents.parquet      # Full documents
│   │   ├── chunks.parquet         # Chunked content (no embeddings)
│   │   ├── manifest.json          # Version metadata
│   │   └── attributions.parquet   # Per-record licensing
│   └── latest/                    # Symlink/copy to current version
└── _registry/
    └── datasets.json              # Global registry
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

Vector Buckets store embedding vectors alongside chunk content, optimized for retrieval via Edge Functions.

### Bucket Structure

```
s3://vector-bucket/
├── {dataset-name}/
│   ├── {version}/
│   │   ├── embeddings.parquet     # Vectors + content
│   │   ├── index/                 # Pre-built HNSW index
│   │   │   ├── index.usearch      # USearch index file
│   │   │   └── metadata.json      # Index parameters
│   │   └── manifest.json          # Version metadata
│   └── latest/
└── _indexes/
    └── hot/                       # Frequently accessed indexes (cached)
        └── {dataset-name}/
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

### Pre-built HNSW Index

Each dataset version includes a pre-built HNSW index for fast similarity search:

```python
#!/usr/bin/env python3
"""
Build HNSW index from embeddings and upload to S3.
"""

import usearch
import numpy as np
import pyarrow.parquet as pq
import boto3
import json

def build_index(dataset: str, version: str):
    """Build and upload HNSW index."""

    # Load embeddings from Vector Bucket
    table = pq.read_table(f's3://vector-bucket/{dataset}/{version}/embeddings.parquet')
    df = table.to_pandas()

    embeddings = np.array(df['embedding'].tolist(), dtype=np.float32)
    chunk_ids = df['chunk_id'].tolist()

    # Build HNSW index
    index = usearch.Index(
        ndim=1536,
        metric='cos',  # Cosine similarity
        dtype='f32',
        connectivity=16,  # M parameter
        expansion_add=128,  # ef_construction
        expansion_search=64  # ef_search
    )

    # Add vectors with their chunk_id indices
    for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, embeddings)):
        index.add(i, embedding)

    # Save index locally
    index.save(f'/tmp/{dataset}_{version}.usearch')

    # Upload to S3
    s3 = boto3.client('s3')
    s3.upload_file(
        f'/tmp/{dataset}_{version}.usearch',
        'vector-bucket',
        f'{dataset}/{version}/index/index.usearch'
    )

    # Upload metadata
    metadata = {
        'ndim': 1536,
        'metric': 'cosine',
        'connectivity': 16,
        'vector_count': len(embeddings),
        'chunk_ids': chunk_ids
    }
    s3.put_object(
        Bucket='vector-bucket',
        Key=f'{dataset}/{version}/index/metadata.json',
        Body=json.dumps(metadata),
        ContentType='application/json'
    )

if __name__ == "__main__":
    build_index('oss-docs', 'v2024.12.1')
```

---

## Edge Functions

Edge Functions provide the search API, loading indexes from S3 and performing similarity search.

### Search Edge Function

```typescript
// supabase/functions/dataset-search/index.ts
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

// In-memory index cache
const indexCache = new Map<string, { index: any; chunkIds: string[]; embeddings: Map<string, any> }>()

interface SearchRequest {
  query: string
  dataset?: string
  version?: string
  limit?: number
  filter?: {
    license?: string[]
  }
}

interface SearchResult {
  chunk_id: string
  content: string
  source_url: string
  similarity: number
  license: string
  metadata?: Record<string, any>
}

async function getEmbedding(text: string): Promise<number[]> {
  const response = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${Deno.env.get('OPENAI_API_KEY')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'text-embedding-3-small',
      input: text,
      dimensions: 1536,
    }),
  })

  const data = await response.json()
  return data.data[0].embedding
}

async function loadDataset(dataset: string, version: string) {
  const cacheKey = `${dataset}:${version}`

  if (indexCache.has(cacheKey)) {
    return indexCache.get(cacheKey)!
  }

  // Load embeddings from S3
  const s3Url = `https://vector-bucket.s3.amazonaws.com/${dataset}/${version}/embeddings.parquet`

  // Using parquet-wasm for Deno
  const { readParquet } = await import('https://esm.sh/parquet-wasm')
  const response = await fetch(s3Url)
  const buffer = await response.arrayBuffer()
  const table = readParquet(new Uint8Array(buffer))

  // Build in-memory structures
  const chunkIds: string[] = []
  const embeddings = new Map<string, { embedding: number[]; content: string; source_url: string; license: string }>()

  for (const row of table) {
    chunkIds.push(row.chunk_id)
    embeddings.set(row.chunk_id, {
      embedding: row.embedding,
      content: row.chunk_content,
      source_url: row.source_url,
      license: row.license,
    })
  }

  const cached = { index: null, chunkIds, embeddings }
  indexCache.set(cacheKey, cached)

  return cached
}

function cosineSimilarity(a: number[], b: number[]): number {
  let dotProduct = 0
  let normA = 0
  let normB = 0

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i]
    normA += a[i] * a[i]
    normB += b[i] * b[i]
  }

  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB))
}

async function search(req: SearchRequest): Promise<SearchResult[]> {
  const { query, dataset = 'oss-docs', version = 'latest', limit = 10, filter } = req

  // Get query embedding
  const queryEmbedding = await getEmbedding(query)

  // Load dataset
  const { embeddings } = await loadDataset(dataset, version)

  // Calculate similarities
  const results: SearchResult[] = []

  for (const [chunkId, data] of embeddings) {
    // Apply license filter
    if (filter?.license && !filter.license.includes(data.license)) {
      continue
    }

    const similarity = cosineSimilarity(queryEmbedding, data.embedding)

    results.push({
      chunk_id: chunkId,
      content: data.content,
      source_url: data.source_url,
      similarity,
      license: data.license,
    })
  }

  // Sort by similarity and return top results
  return results
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, limit)
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      },
    })
  }

  try {
    const body: SearchRequest = await req.json()
    const results = await search(body)

    return new Response(JSON.stringify({ results }), {
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    })
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
})
```

### Optimized Search with USearch

For larger datasets, use pre-built HNSW indexes:

```typescript
// supabase/functions/dataset-search-hnsw/index.ts
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

// USearch WASM binding
const usearch = await import('https://esm.sh/usearch')

interface IndexCache {
  index: any
  chunkIds: string[]
  contentMap: Map<string, any>
}

const indexCache = new Map<string, IndexCache>()

async function loadIndex(dataset: string, version: string): Promise<IndexCache> {
  const cacheKey = `${dataset}:${version}`

  if (indexCache.has(cacheKey)) {
    return indexCache.get(cacheKey)!
  }

  // Load pre-built index from S3
  const indexUrl = `https://vector-bucket.s3.amazonaws.com/${dataset}/${version}/index/index.usearch`
  const metadataUrl = `https://vector-bucket.s3.amazonaws.com/${dataset}/${version}/index/metadata.json`

  const [indexResponse, metadataResponse] = await Promise.all([
    fetch(indexUrl),
    fetch(metadataUrl),
  ])

  const indexBuffer = await indexResponse.arrayBuffer()
  const metadata = await metadataResponse.json()

  // Load index
  const index = new usearch.Index({
    ndim: metadata.ndim,
    metric: 'cos',
    dtype: 'f32',
  })
  index.load(new Uint8Array(indexBuffer))

  // Load content for results
  const embeddingsUrl = `https://vector-bucket.s3.amazonaws.com/${dataset}/${version}/embeddings.parquet`
  const { readParquet } = await import('https://esm.sh/parquet-wasm')
  const embResponse = await fetch(embeddingsUrl)
  const embBuffer = await embResponse.arrayBuffer()
  const table = readParquet(new Uint8Array(embBuffer))

  const contentMap = new Map()
  for (const row of table) {
    contentMap.set(row.chunk_id, {
      content: row.chunk_content,
      source_url: row.source_url,
      license: row.license,
    })
  }

  const cached = { index, chunkIds: metadata.chunk_ids, contentMap }
  indexCache.set(cacheKey, cached)

  return cached
}

async function searchWithIndex(
  query: string,
  dataset: string,
  version: string,
  limit: number
) {
  // Get query embedding
  const queryEmbedding = await getEmbedding(query)

  // Load index
  const { index, chunkIds, contentMap } = await loadIndex(dataset, version)

  // Search
  const results = index.search(new Float32Array(queryEmbedding), limit)

  // Map results to content
  return results.keys.map((idx: number, i: number) => {
    const chunkId = chunkIds[idx]
    const data = contentMap.get(chunkId)

    return {
      chunk_id: chunkId,
      content: data.content,
      source_url: data.source_url,
      similarity: 1 - results.distances[i], // Convert distance to similarity
      license: data.license,
    }
  })
}

serve(async (req) => {
  const { query, dataset = 'oss-docs', version = 'latest', limit = 10 } = await req.json()

  const results = await searchWithIndex(query, dataset, version, limit)

  return new Response(JSON.stringify({ results }), {
    headers: { 'Content-Type': 'application/json' },
  })
})
```

---

## REST API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/datasets` | List all datasets |
| GET | `/v1/{dataset}` | Get dataset metadata |
| GET | `/v1/{dataset}/versions` | List versions |
| POST | `/v1/{dataset}/search` | Semantic search |
| GET | `/v1/{dataset}/download` | Get S3 URLs for direct access |

### Search Request

```http
POST /v1/{dataset}/search
Content-Type: application/json
Authorization: Bearer {anon_key}

{
  "query": "how to implement authentication",
  "limit": 10,
  "version": "latest",
  "filter": {
    "license": ["MIT", "Apache-2.0"]
  },
  "include_embeddings": false
}
```

### Search Response

```json
{
  "results": [
    {
      "chunk_id": "abc123",
      "content": "To implement authentication in your application...",
      "source_url": "https://docs.example.com/auth",
      "similarity": 0.89,
      "license": "MIT",
      "metadata": {
        "title": "Authentication Guide",
        "section": "Getting Started"
      }
    }
  ],
  "meta": {
    "dataset": "oss-docs",
    "version": "v2024.12.1",
    "query_time_ms": 45,
    "total_chunks": 8500000
  }
}
```

### List Datasets

```http
GET /v1/datasets
```

```json
{
  "datasets": [
    {
      "name": "oss-docs",
      "display_name": "OSS Documentation",
      "current_version": "v2024.12.1",
      "record_count": 2000000,
      "license": "MIT",
      "sponsor": {
        "name": "Firecrawl",
        "url": "https://firecrawl.dev"
      }
    }
  ]
}
```

### Download URLs

```http
GET /v1/{dataset}/download?version=v2024.12.1
```

```json
{
  "analytics": {
    "documents": "https://analytics-bucket.s3.amazonaws.com/oss-docs/v2024.12.1/documents.parquet?...",
    "chunks": "https://analytics-bucket.s3.amazonaws.com/oss-docs/v2024.12.1/chunks.parquet?..."
  },
  "vectors": {
    "embeddings": "https://vector-bucket.s3.amazonaws.com/oss-docs/v2024.12.1/embeddings.parquet?...",
    "index": "https://vector-bucket.s3.amazonaws.com/oss-docs/v2024.12.1/index/index.usearch?..."
  },
  "expires_at": "2024-12-31T01:00:00Z"
}
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
import json

def crawl_and_ingest(config):
    """Firecrawl → DuckDB → S3 Pipeline"""

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
| ODbL | ODbL-1.0 | Yes | Required (share-alike) |

### Per-Record Attribution

For datasets with mixed licensing, attribution data is stored in `attributions.parquet`:

```sql
-- Query attributions via DuckDB
SELECT
    a.record_id,
    a.source_url,
    a.license,
    a.attribution_text
FROM read_parquet('s3://analytics-bucket/oss-docs/v2024.12.1/attributions.parquet') a
WHERE a.record_id = 'chunk-123';
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
    Edge Function invocations × $0.000002/invocation
```

### Monitoring

```python
# monitoring.py - Dataset health checks

import boto3
import json
from datetime import datetime, timedelta

def check_dataset_health():
    """Check all datasets for staleness and integrity."""

    s3 = boto3.client('s3')

    # Load registry
    registry = json.loads(
        s3.get_object(Bucket='datasets-registry', Key='registry.json')['Body'].read()
    )

    results = []
    for dataset in registry['datasets']:
        # Check last modified time
        manifest = s3.head_object(
            Bucket='vector-bucket',
            Key=f"{dataset['name']}/{dataset['current_version']}/manifest.json"
        )

        last_modified = manifest['LastModified']
        age_days = (datetime.now(last_modified.tzinfo) - last_modified).days

        status = 'healthy' if age_days < 7 else 'stale'

        results.append({
            'dataset': dataset['name'],
            'version': dataset['current_version'],
            'last_modified': last_modified.isoformat(),
            'age_days': age_days,
            'status': status
        })

    return results
```

---

## Appendix A: SDK Client

```typescript
// @supabase/datasets SDK

interface DatasetClient {
  search(query: string, options?: SearchOptions): Promise<SearchResult[]>
  getMetadata(): Promise<DatasetMetadata>
  listVersions(): Promise<Version[]>
  getDownloadUrls(version?: string): Promise<DownloadUrls>
}

interface SearchOptions {
  limit?: number
  version?: string
  filter?: {
    license?: string[]
  }
}

export function createDatasetClient(
  dataset: string,
  options?: { baseUrl?: string; apiKey?: string }
): DatasetClient {
  const baseUrl = options?.baseUrl ?? 'https://datasets.supabase.co'
  const apiKey = options?.apiKey ?? Deno.env.get('SUPABASE_ANON_KEY')

  return {
    async search(query: string, searchOptions?: SearchOptions) {
      const response = await fetch(`${baseUrl}/v1/${dataset}/search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({ query, ...searchOptions }),
      })

      const data = await response.json()
      return data.results
    },

    async getMetadata() {
      const response = await fetch(`${baseUrl}/v1/${dataset}`, {
        headers: { 'Authorization': `Bearer ${apiKey}` },
      })
      return response.json()
    },

    async listVersions() {
      const response = await fetch(`${baseUrl}/v1/${dataset}/versions`, {
        headers: { 'Authorization': `Bearer ${apiKey}` },
      })
      return response.json()
    },

    async getDownloadUrls(version = 'latest') {
      const response = await fetch(
        `${baseUrl}/v1/${dataset}/download?version=${version}`,
        { headers: { 'Authorization': `Bearer ${apiKey}` } }
      )
      return response.json()
    },
  }
}

// Usage
const docs = createDatasetClient('oss-docs')
const results = await docs.search('authentication', { limit: 5 })
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
