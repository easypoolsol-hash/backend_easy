"""
Snapshot utility functions.
SINGLE RESPONSIBILITY: Hash and compression operations.
"""

import gzip
import hashlib
from typing import List


def calculate_checksum(data: bytes) -> str:
    """
    Calculate SHA-256 checksum of data.

    Args:
        data: Bytes to hash

    Returns:
        Hex digest of SHA-256 hash
    """
    return hashlib.sha256(data).hexdigest()


def compress_snapshot(data: bytes) -> bytes:
    """
    Gzip compress snapshot data.

    Args:
        data: Uncompressed bytes

    Returns:
        Gzip compressed bytes
    """
    return gzip.compress(data, compresslevel=9)


def calculate_content_hash(student_ids: List[str], embedding_ids: List[int]) -> str:
    """
    Calculate content hash for students and embeddings.

    Args:
        student_ids: List of student UUIDs
        embedding_ids: List of embedding IDs

    Returns:
        First 16 characters of SHA-256 hash
    """
    content = (
        f"{len(student_ids)}-{len(embedding_ids)}-" f"{sorted(student_ids)}-{sorted(embedding_ids)}"
    )
    full_hash = hashlib.sha256(content.encode()).hexdigest()
    return full_hash[:16]


def decompress_snapshot(data: bytes) -> bytes:
    """
    Gzip decompress snapshot data.

    Args:
        data: Compressed bytes

    Returns:
        Decompressed bytes
    """
    return gzip.decompress(data)
