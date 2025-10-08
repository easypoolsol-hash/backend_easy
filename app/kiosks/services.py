import hashlib
import json
import os
import sqlite3
import tempfile
from typing import Any

from buses.models import Bus
from students.models import Student


def calculate_content_hash(student_ids: list, embedding_ids: list) -> str:
    """Calculates a stable hash for the content of the snapshot."""
    hash_input = "".join(sorted(map(str, student_ids))) + "".join(
        sorted(map(str, embedding_ids))
    )
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

            self._populate_metadata(
                cursor, student_count, embedding_count, content_hash
            )

            conn.commit()
            conn.close()

            with open(db_path, "rb") as f:
                db_bytes = f.read()

        finally:
            os.remove(db_path)

        metadata = {
            "sync_timestamp": self.sync_timestamp,
            "student_count": student_count,
            "embedding_count": embedding_count,
            "content_hash": content_hash,
        }
        return db_bytes, metadata

    def _create_schema(self, cursor):
        """Creates the necessary tables in the snapshot database."""
        cursor.execute(
            """
            CREATE TABLE students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE embeddings (
                embedding_id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                embedding TEXT NOT NULL, -- Stored as a JSON string of the vector
                model_name TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def _get_data_for_bus(self):
        """Queries the Django database for all necessary student and embedding data."""
        try:
            bus = Bus.objects.get(bus_id=self.bus_id)
        except Bus.DoesNotExist:
            return [], [], []

        students = Student.objects.filter(
            assigned_bus__route=bus.route, status="active"
        ).prefetch_related("photos__face_embeddings")

        student_ids = [s.student_id for s in students]
        embedding_ids = [
            emb.embedding_id
            for s in students
            for p in s.photos.all()
            for emb in p.face_embeddings.all()
        ]

        return students, student_ids, embedding_ids

    def _populate_data(self, cursor, students):
        """Populates the snapshot tables with real data. NO MOCKS."""
        student_rows = []
        embedding_rows = []

        for student in students:
            student_rows.append((str(student.student_id), student.name))

            for photo in student.photos.all():
                for embedding_meta in photo.face_embeddings.all():
                    embedding_json = json.dumps(embedding_meta.embedding)
                    embedding_rows.append(
                        (
                            str(embedding_meta.embedding_id),
                            str(student.student_id),
                            embedding_json,
                            embedding_meta.model_name,
                        )
                    )

        cursor.executemany(
            "INSERT INTO students (student_id, name) VALUES (?, ?)", student_rows
        )
        cursor.executemany(
            "INSERT INTO embeddings (embedding_id, student_id, embedding, model_name) VALUES (?, ?, ?, ?)",
            embedding_rows,
        )

    def _populate_metadata(self, cursor, student_count, embedding_count, content_hash):
        """Stores metadata about the snapshot build."""
        metadata_rows = [
            ("sync_timestamp", self.sync_timestamp),
            ("bus_id", str(self.bus_id)),
            ("student_count", str(student_count)),
            ("embedding_count", str(embedding_count)),
            ("content_hash", content_hash),
        ]
        cursor.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)", metadata_rows
        )
