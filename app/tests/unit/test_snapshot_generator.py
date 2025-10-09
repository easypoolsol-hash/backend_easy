import json
from pathlib import Path
import sqlite3
import tempfile

import pytest

from kiosks.services import SnapshotGenerator
from tests.factories import BusFactory, FaceEmbeddingMetadataFactory, StudentFactory


@pytest.mark.django_db
class TestSnapshotGenerator:
    """Test the new in-memory SnapshotGenerator."""

    def test_snapshot_contains_correct_data(self):
        """Verify snapshot contains correct students and their embeddings for a specific bus."""
        bus1 = BusFactory()
        student1 = StudentFactory(assigned_bus=bus1)
        emb1 = FaceEmbeddingMetadataFactory(
            student_photo__student=student1, embedding=[1.0, 2.0]
        )

        bus2 = BusFactory()
        student2 = StudentFactory(assigned_bus=bus2)  # Belongs to a different bus
        FaceEmbeddingMetadataFactory(student_photo__student=student2)

        # Generate snapshot for bus1
        generator = SnapshotGenerator(bus_id=str(bus1.bus_id))
        snapshot_bytes, _metadata = generator.generate()

        # Write to temp file and verify
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check students table
            cursor.execute("SELECT student_id FROM students")
            student_ids = [row[0] for row in cursor.fetchall()]
            assert len(student_ids) == 1
            assert str(student1.student_id) in student_ids
            assert str(student2.student_id) not in student_ids

            # Check embeddings table
            cursor.execute("SELECT embedding_id, student_id, embedding FROM embeddings")
            embedding_rows = cursor.fetchall()
            assert len(embedding_rows) == 1
            db_emb_id, db_student_id, db_embedding_json = embedding_rows[0]

            assert db_emb_id == str(emb1.embedding_id)
            assert db_student_id == str(student1.student_id)
            assert json.loads(db_embedding_json) == [1.0, 2.0]

            conn.close()
        finally:
            Path(db_path).unlink()

    def test_snapshot_has_valid_metadata(self):
        """Verify the generated snapshot metadata is correct."""
        bus = BusFactory()
        student = StudentFactory(assigned_bus=bus)
        FaceEmbeddingMetadataFactory(student_photo__student=student)

        generator = SnapshotGenerator(bus_id=str(bus.bus_id))
        _, metadata = generator.generate()

        assert "sync_timestamp" in metadata
        assert metadata["student_count"] == 1
        assert metadata["embedding_count"] == 1
        assert "content_hash" in metadata

    def test_snapshot_sqlite_integrity(self):
        """Verify the generated snapshot is a valid SQLite database."""
        bus = BusFactory()
        StudentFactory(assigned_bus=bus)

        generator = SnapshotGenerator(bus_id=str(bus.bus_id))
        snapshot_bytes, _ = generator.generate()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            assert result == "ok"
            conn.close()
        finally:
            Path(db_path).unlink()

    def test_snapshot_has_correct_schema(self):
        """Verify the generated SQLite file has the correct table schema."""
        bus = BusFactory()
        generator = SnapshotGenerator(bus_id=str(bus.bus_id))
        snapshot_bytes, _ = generator.generate()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            assert {"students", "embeddings", "metadata"}.issubset(tables)

            conn.close()
        finally:
            Path(db_path).unlink()
