import hashlib
import os
import sqlite3
import struct
import tempfile
from typing import Any

from buses.models import Bus
from students.models import Student


def calculate_content_hash(student_ids: list, embedding_ids: list) -> str:
    """Calculates a stable hash for the content of the snapshot."""
    hash_input = "".join(sorted(map(str, student_ids))) + "".join(sorted(map(str, embedding_ids)))
    # Use SHA-256 for collision resistance (avoid MD5)
    return hashlib.sha256(hash_input.encode()).hexdigest()


class SnapshotGenerator:
    """Creates a portable, secure SQLite database snapshot for a given bus."""

    def __init__(self, bus_id: Any):
        from django.utils import timezone as dj_tz

        # Accept strings or UUIDs and normalise to str for filenames/IDs
        self.bus_id = str(bus_id)
        # Use timezone-aware timestamp
        self.sync_timestamp = dj_tz.now().isoformat()

    def generate(self) -> tuple[bytes, dict]:
        """
        Generates the SQLite database and returns it as bytes.
        """
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            self._create_schema(cursor)
            students, student_ids, embedding_ids = self._get_data_for_bus()
            self._populate_data(cursor, students)

            student_count = len(student_ids)
            embedding_count = len(embedding_ids)
            content_hash = calculate_content_hash(student_ids, embedding_ids)

            self._populate_metadata(cursor, student_count, embedding_count, content_hash)

            conn.commit()
            conn.close()
            # Explicitly delete connection to ensure file handle is released on Windows
            del conn
            del cursor

            with open(db_path, "rb") as f:
                db_bytes = f.read()

        finally:
            # Force garbage collection to ensure file handles are released
            import gc

            gc.collect()
            try:
                os.remove(db_path)
            except OSError:
                # If file is still locked, wait a bit and try again
                import time

                time.sleep(0.1)
                os.remove(db_path)

        metadata = {
            "sync_timestamp": self.sync_timestamp,
            "student_count": student_count,
            "embedding_count": embedding_count,
            "content_hash": content_hash,
        }
        return db_bytes, metadata

    def _create_schema(self, cursor):
        """Creates schema following snapshot_interface_contract.yaml"""
        cursor.execute(
            """
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                bus_id TEXT
            )
            """
        )
        cursor.execute("CREATE INDEX idx_students_status ON students(status)")
        cursor.execute("CREATE INDEX idx_students_bus ON students(bus_id)")

        cursor.execute(
            """
            CREATE TABLE face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                embedding_vector BLOB NOT NULL,
                quality_score REAL NOT NULL,
                model_name TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            """
        )
        cursor.execute("CREATE INDEX idx_embeddings_student ON face_embeddings(student_id)")

        cursor.execute(
            """
            CREATE TABLE sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def _get_data_for_bus(self):
        """Queries the Django database for all necessary student and embedding data.

        Returns ALL students (not just bus-specific) for fast offline matching.
        Each kiosk gets full database to identify wrong-bus students instantly.
        """
        try:
            Bus.objects.get(bus_id=self.bus_id)  # Verify bus exists
        except Bus.DoesNotExist:
            return [], [], []

        # Get ALL active students across all buses for offline speed
        students = Student.objects.filter(status="active").prefetch_related("photos__face_embeddings", "assigned_bus")

        student_ids = [s.student_id for s in students]
        embedding_ids = [emb.embedding_id for s in students for p in s.photos.all() for emb in p.face_embeddings.all()]

        return students, student_ids, embedding_ids

    def _populate_data(self, cursor, students):
        """Populates snapshot following contract: binary embeddings, decrypted names."""
        student_rows = []
        embedding_rows = []

        for student in students:
            # Contract: names must be decrypted
            decrypted_name = student.encrypted_name
            bus_id = str(student.assigned_bus.bus_id) if student.assigned_bus else None
            student_rows.append((str(student.student_id), decrypted_name, "active", bus_id))

            for photo in student.photos.all():
                for embedding_meta in photo.face_embeddings.all():
                    # Contract: convert JSON list to binary BLOB (192 floats, little-endian)
                    embedding_list = embedding_meta.embedding  # List[float] from JSONField
                    embedding_blob = struct.pack(f"{len(embedding_list)}f", *embedding_list)

                    embedding_rows.append(
                        (
                            str(student.student_id),
                            embedding_blob,
                            embedding_meta.quality_score,
                            embedding_meta.model_name,
                        )
                    )

        cursor.executemany("INSERT INTO students (student_id, name, status, bus_id) VALUES (?, ?, ?, ?)", student_rows)
        cursor.executemany(
            "INSERT INTO face_embeddings (student_id, embedding_vector, quality_score, model_name) VALUES (?, ?, ?, ?)",
            embedding_rows,
        )

    def _populate_metadata(self, cursor, student_count, embedding_count, content_hash):
        """Stores metadata following contract required_keys."""
        metadata_rows = [
            ("schema_version", "1.0.0"),
            ("sync_timestamp", self.sync_timestamp),
            ("bus_id", str(self.bus_id)),
            ("student_count", str(student_count)),
            ("embedding_count", str(embedding_count)),
            ("content_hash", content_hash),
        ]
        cursor.executemany("INSERT INTO sync_metadata (key, value) VALUES (?, ?)", metadata_rows)
