"""
Unit tests for SnapshotGenerator - Critical sync functionality
Fortune 500 standard: Test data integrity
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.kiosks.services.snapshot_generator import SnapshotGenerator
from app.tests.factories import BusFactory, FaceEmbeddingFactory, StudentFactory


@pytest.mark.django_db
class TestSnapshotGenerator:
    """Test snapshot generation creates valid SQLite databases"""

    def test_snapshot_contains_correct_students(self):
        """CRITICAL: Snapshot must only contain students for the specific bus"""
        # Create bus with students
        bus = BusFactory()
        student1 = StudentFactory(plaintext_name="Student 1")
        student2 = StudentFactory(plaintext_name="Student 2")
        other_student = StudentFactory(plaintext_name="Other Student")

        # Assign students to bus
        bus.students.add(student1, student2)

        # Generate snapshot
        generator = SnapshotGenerator(bus_id=bus.bus_id)
        snapshot_bytes, metadata = generator.generate()

        # Write to temp file and verify
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Verify only correct students
            cursor.execute("SELECT student_id FROM students ORDER BY student_id")
            student_ids = [row[0] for row in cursor.fetchall()]

            assert student1.student_id in student_ids
            assert student2.student_id in student_ids
            assert other_student.student_id not in student_ids
            assert len(student_ids) == 2

            conn.close()
        finally:
            Path(db_path).unlink()

    def test_snapshot_contains_all_embeddings(self):
        """CRITICAL: Snapshot must include all embeddings per student"""
        # Create bus with student and multiple embeddings
        bus = BusFactory()
        student = StudentFactory(plaintext_name="Multi Embedding Student")
        bus.students.add(student)

        # Create 3 embeddings for student
        emb1 = FaceEmbeddingFactory(student=student)
        emb2 = FaceEmbeddingFactory(student=student)
        emb3 = FaceEmbeddingFactory(student=student)

        # Generate snapshot
        generator = SnapshotGenerator(bus_id=bus.bus_id)
        snapshot_bytes, metadata = generator.generate()

        # Verify
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Count embeddings
            cursor.execute(
                "SELECT COUNT(*) FROM face_embeddings WHERE student_id = ?",
                (student.student_id,)
            )
            count = cursor.fetchone()[0]

            assert count == 3, f"Expected 3 embeddings, got {count}"

            # Verify embedding data is BLOB
            cursor.execute("SELECT embedding_data FROM face_embeddings LIMIT 1")
            blob = cursor.fetchone()[0]
            assert isinstance(blob, bytes)
            assert len(blob) == 768  # 192 floats * 4 bytes

            conn.close()
        finally:
            Path(db_path).unlink()

    def test_snapshot_has_valid_metadata(self):
        """CRITICAL: Snapshot must include sync metadata"""
        bus = BusFactory()
        student = StudentFactory()
        bus.students.add(student)
        FaceEmbeddingFactory(student=student)

        generator = SnapshotGenerator(bus_id=bus.bus_id)
        snapshot_bytes, metadata = generator.generate()

        # Verify metadata dict
        assert 'sync_timestamp' in metadata
        assert 'bus_id' in metadata
        assert 'student_count' in metadata
        assert 'embedding_count' in metadata
        assert 'content_hash' in metadata

        assert metadata['bus_id'] == bus.bus_id
        assert metadata['student_count'] == 1
        assert metadata['embedding_count'] == 1

        # Verify metadata in SQLite
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT key, value FROM sync_metadata")
            db_metadata = dict(cursor.fetchall())

            assert 'sync_timestamp' in db_metadata
            assert 'bus_id' in db_metadata
            assert db_metadata['bus_id'] == bus.bus_id

            conn.close()
        finally:
            Path(db_path).unlink()

    def test_snapshot_sqlite_integrity(self):
        """CRITICAL: Generated SQLite must pass integrity check"""
        bus = BusFactory()
        student = StudentFactory()
        bus.students.add(student)

        generator = SnapshotGenerator(bus_id=bus.bus_id)
        snapshot_bytes, _ = generator.generate()

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            f.write(snapshot_bytes)
            db_path = f.name

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # SQLite integrity check
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]

            assert result == 'ok', f"SQLite integrity check failed: {result}"

            conn.close()
        finally:
            Path(db_path).unlink()
