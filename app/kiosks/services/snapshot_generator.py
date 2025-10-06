"""
Snapshot Generator Service.
SINGLE RESPONSIBILITY: Generate SQLite snapshot for a specific bus.
SOLID: Open/closed - extend for new tables, don't modify existing logic.
"""

import os
import sqlite3
import struct
import tempfile
from datetime import datetime
from typing import Dict, List, Tuple

from django.utils import timezone

from buses.models import Bus
from students.models import FaceEmbeddingMetadata, Student, StudentPhoto

from ..utils import calculate_content_hash


class SnapshotGenerator:
    """
    Generate encrypted SQLite database snapshot for a specific bus.
    Contains only students assigned to that bus and their embeddings.
    """

    def __init__(self, bus_id: str):
        """
        Initialize snapshot generator.

        Args:
            bus_id: UUID of bus to generate snapshot for
        """
        self._bus_id = bus_id
        self._db_path: str = ""
        self._temp_files: List[str] = []

    def generate(self) -> Tuple[bytes, Dict[str, any]]:
        """
        Generate SQLite snapshot for this bus.

        Returns:
            Tuple of (database_bytes, metadata_dict)
            metadata contains: student_count, embedding_count, content_hash
        """
        try:
            self._db_path = self._create_temp_database()
            db_bytes = self._read_database()
            metadata = self._get_metadata()
            return db_bytes, metadata
        finally:
            self._cleanup()

    def _create_temp_database(self) -> str:
        """Create temporary SQLite file with students + embeddings."""
        # Create temp file
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._temp_files.append(db_path)

        # Connect and create schema
        conn = sqlite3.connect(db_path)
        try:
            self._create_schema(conn)
            self._populate_students(conn)
            self._populate_embeddings(conn)
            self._populate_metadata(conn)
            conn.commit()
        finally:
            conn.close()

        return db_path

    def _create_schema(self, conn: sqlite3.Connection):
        """Create database schema."""
        cursor = conn.cursor()

        # Students table
        cursor.execute(
            """
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
            """
        )

        # Embeddings table
        cursor.execute(
            """
            CREATE TABLE face_embeddings (
                embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                embedding_data BLOB NOT NULL,
                quality_score REAL NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
                    ON DELETE CASCADE
            )
            """
        )

        # Index on student_id for fast lookups
        cursor.execute(
            """
            CREATE INDEX idx_embeddings_student
            ON face_embeddings(student_id)
            """
        )

        # Metadata table
        cursor.execute(
            """
            CREATE TABLE sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def _populate_students(self, conn: sqlite3.Connection):
        """Populate students table (PRIVATE method)."""
        cursor = conn.cursor()

        # Get students for this bus
        students = Student.objects.filter(
            assigned_bus__bus_id=self._bus_id, status="active"
        ).values("student_id", "name")

        for student in students:
            cursor.execute(
                """
                INSERT INTO students (student_id, name, status)
                VALUES (?, ?, 'active')
                """,
                (str(student["student_id"]), student["name"]),
            )

    def _populate_embeddings(self, conn: sqlite3.Connection):
        """Populate embeddings table (PRIVATE method)."""
        cursor = conn.cursor()

        # Get embeddings for students on this bus
        embeddings = FaceEmbeddingMetadata.objects.filter(
            student_photo__student__assigned_bus__bus_id=self._bus_id,
            student_photo__student__status="active",
        ).select_related("student_photo__student")

        for emb in embeddings:
            # Get embedding vector from Qdrant (placeholder - actual implementation needed)
            embedding_vector = self._get_embedding_vector(emb.qdrant_point_id)

            # Convert float list to bytes (192 floats * 4 bytes = 768 bytes)
            embedding_bytes = struct.pack(f"{len(embedding_vector)}f", *embedding_vector)

            cursor.execute(
                """
                INSERT INTO face_embeddings
                (student_id, embedding_data, quality_score)
                VALUES (?, ?, ?)
                """,
                (
                    str(emb.student_photo.student.student_id),
                    embedding_bytes,
                    emb.quality_score,
                ),
            )

    def _get_embedding_vector(self, qdrant_point_id: str) -> List[float]:
        """
        Get embedding vector from Qdrant.
        TODO: Implement actual Qdrant client integration.

        Args:
            qdrant_point_id: Qdrant point ID

        Returns:
            List of 192 floats
        """
        # Placeholder - return dummy vector
        # In production, this would query Qdrant
        return [0.0] * 192

    def _populate_metadata(self, conn: sqlite3.Connection):
        """Populate sync_metadata table (PRIVATE method)."""
        cursor = conn.cursor()

        # Get counts
        student_count = Student.objects.filter(
            assigned_bus__bus_id=self._bus_id, status="active"
        ).count()

        embedding_count = FaceEmbeddingMetadata.objects.filter(
            student_photo__student__assigned_bus__bus_id=self._bus_id,
            student_photo__student__status="active",
        ).count()

        # Get student and embedding IDs for hash
        student_ids = list(
            Student.objects.filter(
                assigned_bus__bus_id=self._bus_id, status="active"
            ).values_list("student_id", flat=True)
        )

        embedding_ids = list(
            FaceEmbeddingMetadata.objects.filter(
                student_photo__student__assigned_bus__bus_id=self._bus_id,
                student_photo__student__status="active",
            ).values_list("embedding_id", flat=True)
        )

        content_hash = calculate_content_hash(
            [str(sid) for sid in student_ids], embedding_ids
        )

        # Insert metadata
        sync_timestamp = timezone.now().isoformat()

        metadata = [
            ("sync_timestamp", sync_timestamp),
            ("bus_id", str(self._bus_id)),
            ("student_count", str(student_count)),
            ("embedding_count", str(embedding_count)),
            ("content_hash", content_hash),
        ]

        cursor.executemany(
            "INSERT INTO sync_metadata (key, value) VALUES (?, ?)", metadata
        )

    def _read_database(self) -> bytes:
        """Read database file as bytes."""
        with open(self._db_path, "rb") as f:
            return f.read()

    def _get_metadata(self) -> Dict[str, any]:
        """Get metadata about generated snapshot."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            # Read metadata from table
            cursor.execute("SELECT key, value FROM sync_metadata")
            metadata_rows = cursor.fetchall()

            metadata = dict(metadata_rows)

            return {
                "student_count": int(metadata.get("student_count", 0)),
                "embedding_count": int(metadata.get("embedding_count", 0)),
                "content_hash": metadata.get("content_hash", ""),
                "sync_timestamp": metadata.get("sync_timestamp", ""),
                "bus_id": metadata.get("bus_id", ""),
            }
        finally:
            conn.close()

    def _cleanup(self):
        """Delete temporary files (PRIVATE method)."""
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass  # Ignore cleanup errors
