# Supabase Open Datasets

Public, versioned embedding datasets hosted in Vector Buckets — queryable via SQL and REST.

## Overview

Supabase Open Datasets provides pre-crawled, pre-chunked, and pre-embedded datasets ready for RAG (Retrieval Augmented Generation) applications. Skip the data pipeline and start building immediately.

**Key Features:**
- **Instant RAG** — No crawling, chunking, or embedding required
- **SQL Native** — Query with pgvector via standard PostgreSQL
- **REST API** — Access embeddings via PostgREST
- **Immutable Versions** — Reproducible retrieval with checksums
- **Permissive Licenses** — SPDX-compliant, per-record attribution

## Quick Start

### 1. Connect to a Dataset

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Link to the public dataset
SELECT supabase.link_dataset('oss-docs', version := 'latest');
```

### 2. Query with Semantic Search

```sql
-- Find relevant documentation
SELECT
  content,
  metadata->>'source' AS source,
  1 - (embedding <=> query_embedding) AS similarity
FROM oss_docs.chunks
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

### 3. Use the REST API

```bash
curl -X POST 'https://api.supabase.com/datasets/v1/oss-docs/query' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"query": "how to create a table", "limit": 10}'
```

## Available Datasets

### Documentation & Knowledge

| Dataset | Description | Records | Embedder | License | Sponsor |
|---------|-------------|---------|----------|---------|---------|
| `oss-docs` | OSS documentation (React, Vue, Next.js, etc.) | ~2M | text-embedding-3-small | MIT/Apache | [Firecrawl](https://firecrawl.dev) |
| `postgres-mailing-lists` | PostgreSQL mailing list archives | ~1.5M | text-embedding-3-small | PostgreSQL | Supabase |
| `hacker-news` | HN stories, comments, and discussions | ~5M | text-embedding-3-small | CC BY-NC | [Firecrawl](https://firecrawl.dev) |
| `arxiv-abstracts` | arXiv paper abstracts and metadata | ~2.3M | text-embedding-3-small | CC0 | Supabase |

### Standards & Specifications

| Dataset | Description | Records | Embedder | License | Sponsor |
|---------|-------------|---------|----------|---------|---------|
| `rfc-repository` | IETF RFCs, Rust RFCs, Python PEPs | ~50K | text-embedding-3-small | Various | [Firecrawl](https://firecrawl.dev) |
| `regulations` | US CFR, EU regulations, amendments | ~500K | text-embedding-3-small | Public Domain | Supabase |
| `patents-us` | USPTO patent abstracts and claims | ~10M | text-embedding-3-small | Public Domain | Supabase |

### Code & Development

| Dataset | Description | Records | Embedder | License | Sponsor |
|---------|-------------|---------|----------|---------|---------|
| `code-samples` | Permissive code samples from GitHub | ~5M | text-embedding-3-small | MIT/Apache | [Firecrawl](https://firecrawl.dev) |
| `release-notes` | Changelogs from popular GitHub projects | ~200K | text-embedding-3-small | Various | [Firecrawl](https://firecrawl.dev) |
| `status-pages` | Historical status updates from major providers | ~100K | text-embedding-3-small | Various | Supabase |

### Business & Finance

| Dataset | Description | Records | Embedder | License | Sponsor |
|---------|-------------|---------|----------|---------|---------|
| `earnings-transcripts` | Public company earnings call transcripts | ~500K | text-embedding-3-small | Fair Use | Supabase |
| `job-postings` | Aggregated public job board listings | ~2M | text-embedding-3-small | Various | [Firecrawl](https://firecrawl.dev) |
| `commerce-catalog` | Synthetic e-commerce product catalog | ~1M | text-embedding-3-small | CC0 | Supabase |

### Geospatial

| Dataset | Description | Records | Embedder | License | Sponsor |
|---------|-------------|---------|----------|---------|---------|
| `osm-places` | OpenStreetMap POIs with embeddings | ~50M | text-embedding-3-small | ODbL | [Protomaps](https://protomaps.com) |
| `geonames` | Geographic names and descriptions | ~12M | text-embedding-3-small | CC BY | [Protomaps](https://protomaps.com) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Supabase Dashboard                        │
│                    "Sponsored by Firecrawl"                      │
└─────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
         ┌──────────────────┐        ┌──────────────────┐
         │   Analytics       │        │   Vector         │
         │   Buckets         │        │   Buckets        │
         │   (Raw Data)      │        │   (Embeddings)   │
         └────────┬─────────┘        └────────┬─────────┘
                  │                           │
                  └─────────────┬─────────────┘
                                ▼
                    ┌──────────────────┐
                    │    pgvector      │
                    │   HNSW/IVFFLAT   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │   SQL    │  │  REST    │  │  Edge    │
        │  Client  │  │  API     │  │ Functions│
        └──────────┘  └──────────┘  └──────────┘
```

## Versioning

Each dataset follows semantic versioning with immutable snapshots:

```sql
-- List available versions
SELECT * FROM supabase.dataset_versions('oss-docs');

-- Pin to a specific version
SELECT supabase.link_dataset('oss-docs', version := 'v2024.12.1');

-- Check version metadata
SELECT
  version,
  record_count,
  embedding_model,
  checksum,
  created_at
FROM supabase.dataset_metadata('oss-docs');
```

## Sponsorship

Interested in sponsoring a dataset? Sponsors receive:

- Logo placement in Dashboard dataset browser
- Attribution in dataset metadata
- Co-marketing opportunities
- Priority for dataset update scheduling

Contact [partnerships@supabase.io](mailto:partnerships@supabase.io) for details.

## Launch Partners

<p align="center">
  <a href="https://firecrawl.dev"><img src="https://firecrawl.dev/logo.svg" height="40" alt="Firecrawl"></a>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <a href="https://protomaps.com"><img src="https://protomaps.com/logo.svg" height="40" alt="Protomaps"></a>
</p>

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines on:

- Proposing new datasets
- Reporting data quality issues
- Submitting attribution corrections

## License

Dataset-specific licenses are documented in the registry. This repository is licensed under Apache-2.0.

## Links

- [Technical Specification](./SPEC.md)
- [Dataset Registry Schema](./SPEC.md#dataset-registry)
- [API Reference](https://supabase.com/docs/guides/datasets)
- [Status Page](https://status.supabase.com)
