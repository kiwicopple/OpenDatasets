"""
OpenDatasets - Public embedding datasets for RAG applications.

Modules:
    scraper: Web scraping utilities
    chunker: Text chunking and embedding
    iceberg: Supabase Analytics Bucket (Iceberg) operations
    vector: Supabase Vector Bucket operations
"""

__version__ = "0.1.0"

from opendatasets.scraper import Scraper
from opendatasets.chunker import Chunker, embed_texts
from opendatasets.iceberg import IcebergClient
from opendatasets.vector import VectorClient

__all__ = [
    "Scraper",
    "Chunker",
    "embed_texts",
    "IcebergClient",
    "VectorClient",
]
