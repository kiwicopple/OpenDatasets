# Supabase Open Datasets

Public, versioned embedding datasets hosted in S3-compatible buckets — queryable via Edge Functions and REST.

## Overview

Supabase Open Datasets provides pre-crawled, pre-chunked, and pre-embedded datasets ready for RAG (Retrieval Augmented Generation) applications. Skip the data pipeline and start building immediately.

**Key Features:**
- **Instant RAG** — No crawling, chunking, or embedding required
- **S3 Native** — Parquet files in Analytics Buckets and Vector Buckets
- **Edge Functions** — Low-latency semantic search at the edge
- **Immutable Versions** — Reproducible retrieval with checksums
- **Permissive Licenses** — SPDX-compliant, per-record attribution

## Quick Start

### 1. Search via REST API

```bash
curl -X POST 'https://datasets.supabase.co/v1/oss-docs/search' \
  -H 'Authorization: Bearer YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "how to create a table",
    "limit": 10
  }'
```

### 2. Use in Your Edge Function

```typescript
import { searchDataset } from 'https://esm.sh/@supabase/datasets'

Deno.serve(async (req) => {
  const { query } = await req.json()

  const results = await searchDataset('oss-docs', {
    query,
    limit: 10,
    version: 'latest'
  })

  return Response.json({ results })
})
```

### 3. Direct Parquet Access via DuckDB

```sql
-- Query embeddings directly from S3
SELECT chunk_id, chunk_content, embedding
FROM read_parquet('s3://vector-bucket/oss-docs/v2024.12.1/embeddings.parquet')
LIMIT 10;
```

## Available Datasets

### Documentation & Knowledge

| Dataset | Description | Records | Embedder | License | Sponsor |
|---------|-------------|---------|----------|---------|---------|
| `oss-docs` | OSS documentation (React, Vue, Next.js, etc.) | ~2M | text-embedding-3-small | MIT/Apache | [Firecrawl](https://firecrawl.dev) |
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
         │   Buckets (S3)    │        │   Buckets (S3)   │
         │                   │        │                   │
         │  • Raw documents  │        │  • Embeddings     │
         │  • Metadata       │        │  • Chunk content  │
         │  • Parquet format │        │  • Parquet format │
         └────────┬─────────┘        └────────┬─────────┘
                  │                           │
                  └─────────────┬─────────────┘
                                ▼
                    ┌──────────────────┐
                    │  Edge Functions   │
                    │  (Search API)     │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │  REST    │  │  SDK     │  │  DuckDB  │
        │  API     │  │  Client  │  │  Direct  │
        └──────────┘  └──────────┘  └──────────┘
```

## Versioning

Each dataset follows semantic versioning with immutable snapshots:

```bash
# List available versions
curl 'https://datasets.supabase.co/v1/oss-docs/versions'

# Search a specific version
curl -X POST 'https://datasets.supabase.co/v1/oss-docs/search?version=v2024.12.1' \
  -H 'Content-Type: application/json' \
  -d '{"query": "authentication"}'

# Get dataset metadata
curl 'https://datasets.supabase.co/v1/oss-docs/metadata'
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
