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
        """Verify snapshot contains ALL students (not bus-specific) with bus_id for cross-bus recognition."""
        bus1 = BusFactory()
        student1 = StudentFactory(assigned_bus=bus1)
        FaceEmbeddingMetadataFactory(student_photo__student=student1, embedding=[1.0, 2.0])

        bus2 = BusFactory()
        student2 = StudentFactory(assigned_bus=bus2)  # Different bus
        FaceEmbeddingMetadataFactory(student_photo__student=student2, embedding=[3.0, 4.0])

        # Generate snapshot for bus1 - should include ALL students
        generator = SnapshotGenerator(bus_id=str(bus1.bus_id))  # type: ignore[attr-defined]
        snapshot_bytes, _metadata = generator.generate()

        # Write to temp file and verify
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check students table - should contain BOTH students (all buses)
            cursor.execute("SELECT student_id, bus_id FROM students")
            students = {row[0]: row[1] for row in cursor.fetchall()}
            assert len(students) == 2  # Changed: includes all students
            assert str(student1.student_id) in students  # type: ignore[attr-defined]
            assert str(student2.student_id) in students  # type: ignore[attr-defined]

            # Verify bus_id column is populated correctly
            assert students[str(student1.student_id)] == str(bus1.bus_id)  # type: ignore[attr-defined]
            assert students[str(student2.student_id)] == str(bus2.bus_id)  # type: ignore[attr-defined]

            # Check face_embeddings table - should have embeddings for both students
            cursor.execute("SELECT id, student_id, embedding_vector, quality_score FROM face_embeddings")
            embedding_rows = cursor.fetchall()
            assert len(embedding_rows) == 2  # Changed: includes all embeddings

            # Verify first embedding
            db_emb_id, _db_student_id, db_embedding_blob, _db_quality = embedding_rows[0]
            assert isinstance(db_emb_id, int)  # INTEGER AUTOINCREMENT

            # Verify binary BLOB format (2 floats = 8 bytes)
            assert isinstance(db_embedding_blob, bytes)
            assert len(db_embedding_blob) == 8  # 2 floats * 4 bytes

            conn.close()
        finally:
            Path(db_path).unlink()

    def test_snapshot_has_valid_metadata(self):
        """Verify the generated snapshot metadata is correct (includes all students)."""
        bus1 = BusFactory()
        student1 = StudentFactory(assigned_bus=bus1)
        FaceEmbeddingMetadataFactory(student_photo__student=student1)

        bus2 = BusFactory()
        student2 = StudentFactory(assigned_bus=bus2)
        FaceEmbeddingMetadataFactory(student_photo__student=student2)

        generator = SnapshotGenerator(bus_id=str(bus1.bus_id))  # type: ignore[attr-defined]
        _, metadata = generator.generate()

        assert "sync_timestamp" in metadata
        assert metadata["student_count"] == 2  # Changed: includes all students
        assert metadata["embedding_count"] == 2  # Changed: includes all embeddings
        assert "content_hash" in metadata

    def test_snapshot_sqlite_integrity(self):
        """Verify the generated snapshot is a valid SQLite database."""
        bus = BusFactory()
        StudentFactory(assigned_bus=bus)

        generator = SnapshotGenerator(bus_id=str(bus.bus_id))  # type: ignore[attr-defined]
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
        generator = SnapshotGenerator(bus_id=str(bus.bus_id))  # type: ignore[attr-defined]
        snapshot_bytes, _ = generator.generate()

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            assert {"students", "face_embeddings", "sync_metadata"}.issubset(tables)

            conn.close()
        finally:
            Path(db_path).unlink()
