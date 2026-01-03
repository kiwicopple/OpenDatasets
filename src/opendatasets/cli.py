"""
Command-line interface for OpenDatasets.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="OpenDatasets - Public embedding datasets for RAG",
        prog="opendatasets",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape a website")
    scrape_parser.add_argument("url", help="URL to scrape")
    scrape_parser.add_argument("--max-pages", type=int, default=10, help="Max pages to crawl")
    scrape_parser.add_argument("--output", "-o", default="output.jsonl", help="Output file")

    # Chunk command
    chunk_parser = subparsers.add_parser("chunk", help="Chunk documents")
    chunk_parser.add_argument("input", help="Input file (JSONL)")
    chunk_parser.add_argument("--output", "-o", default="chunks.jsonl", help="Output file")
    chunk_parser.add_argument("--size", type=int, default=1000, help="Chunk size")
    chunk_parser.add_argument("--overlap", type=int, default=200, help="Chunk overlap")

    # Embed command
    embed_parser = subparsers.add_parser("embed", help="Generate embeddings")
    embed_parser.add_argument("input", help="Input file (JSONL with chunks)")
    embed_parser.add_argument("--output", "-o", default="embeddings.parquet", help="Output file")
    embed_parser.add_argument("--model", default="text-embedding-3-small", help="Embedding model")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload to Supabase")
    upload_parser.add_argument("input", help="Input Parquet file")
    upload_parser.add_argument("--dataset", required=True, help="Dataset name")
    upload_parser.add_argument("--version", required=True, help="Version string")
    upload_parser.add_argument("--bucket", choices=["vector", "iceberg"], default="vector")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # TODO: Implement command handlers
    print(f"Command: {args.command}")
    print(f"Args: {args}")


if __name__ == "__main__":
    main()
