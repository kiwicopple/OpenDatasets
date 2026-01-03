"""
Text chunking and embedding utilities.

Supports:
- Fixed-size chunking with overlap
- Semantic chunking (sentence-aware)
- OpenAI embeddings
"""

import os
import re
from dataclasses import dataclass
from typing import Iterator

from pydantic import BaseModel


class Chunk(BaseModel):
    """A text chunk with optional embedding."""

    id: str
    doc_id: str
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    embedding: list[float] | None = None
    metadata: dict = {}


@dataclass
class Chunker:
    """
    Text chunker with configurable strategy.

    Example:
        chunker = Chunker(chunk_size=1000, overlap=200)
        chunks = list(chunker.chunk(doc_id="doc1", text="...long text..."))
    """

    chunk_size: int = 1000
    overlap: int = 200
    strategy: str = "fixed"  # "fixed" or "sentence"
    min_chunk_size: int = 50

    def chunk(self, doc_id: str, text: str, metadata: dict = None) -> Iterator[Chunk]:
        """
        Split text into chunks.

        Args:
            doc_id: Document identifier
            text: Text to chunk
            metadata: Optional metadata to attach to chunks

        Yields:
            Chunk objects
        """
        if self.strategy == "sentence":
            yield from self._chunk_by_sentence(doc_id, text, metadata or {})
        else:
            yield from self._chunk_fixed(doc_id, text, metadata or {})

    def _chunk_fixed(self, doc_id: str, text: str, metadata: dict) -> Iterator[Chunk]:
        """Fixed-size chunking with overlap."""
        text = text.strip()
        if len(text) < self.min_chunk_size:
            return

        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to break at word boundary
            if end < len(text):
                # Look back for a space
                last_space = text.rfind(" ", start, end)
                if last_space > start + self.chunk_size // 2:
                    end = last_space

            chunk_text = text[start:end].strip()

            if len(chunk_text) >= self.min_chunk_size:
                yield Chunk(
                    id=f"{doc_id}_{chunk_index}",
                    doc_id=doc_id,
                    content=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata=metadata,
                )
                chunk_index += 1

            # Move forward, accounting for overlap
            start = end - self.overlap
            if start >= len(text) - self.min_chunk_size:
                break

    def _chunk_by_sentence(self, doc_id: str, text: str, metadata: dict) -> Iterator[Chunk]:
        """Sentence-aware chunking."""
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        current_chunk = []
        current_length = 0
        start_char = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if current_length + sentence_len > self.chunk_size and current_chunk:
                # Emit current chunk
                chunk_text = " ".join(current_chunk)
                yield Chunk(
                    id=f"{doc_id}_{chunk_index}",
                    doc_id=doc_id,
                    content=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata=metadata,
                )
                chunk_index += 1

                # Keep overlap sentences
                overlap_text = ""
                overlap_sentences = []
                for s in reversed(current_chunk):
                    if len(overlap_text) + len(s) < self.overlap:
                        overlap_sentences.insert(0, s)
                        overlap_text = " ".join(overlap_sentences)
                    else:
                        break

                current_chunk = overlap_sentences
                current_length = len(overlap_text)
                start_char += len(chunk_text) - len(overlap_text)

            current_chunk.append(sentence)
            current_length += sentence_len + 1  # +1 for space

        # Emit final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size:
                yield Chunk(
                    id=f"{doc_id}_{chunk_index}",
                    doc_id=doc_id,
                    content=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata=metadata,
                )


def embed_texts(
    texts: list[str],
    model: str = "text-embedding-3-small",
    dimensions: int = 1536,
    batch_size: int = 100,
) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using OpenAI.

    Args:
        texts: List of texts to embed
        model: OpenAI embedding model
        dimensions: Embedding dimensions
        batch_size: Texts per API call

    Returns:
        List of embedding vectors
    """
    import openai

    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            model=model,
            input=batch,
            dimensions=dimensions,
        )
        embeddings.extend([e.embedding for e in response.data])

    return embeddings


def embed_chunks(
    chunks: list[Chunk],
    model: str = "text-embedding-3-small",
    dimensions: int = 1536,
) -> list[Chunk]:
    """
    Add embeddings to chunks.

    Args:
        chunks: List of Chunk objects
        model: OpenAI embedding model
        dimensions: Embedding dimensions

    Returns:
        Chunks with embeddings added
    """
    texts = [chunk.content for chunk in chunks]
    embeddings = embed_texts(texts, model=model, dimensions=dimensions)

    result = []
    for chunk, embedding in zip(chunks, embeddings):
        result.append(chunk.model_copy(update={"embedding": embedding}))

    return result
