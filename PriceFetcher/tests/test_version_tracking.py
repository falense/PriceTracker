"""Tests for git utilities and version tracking."""

import pytest
import sqlite3
import tempfile
import json
from pathlib import Path
from datetime import datetime

from src.git_utils import get_current_commit_hash, get_commit_info
from src.storage import PriceStorage


class TestGitUtils:
    """Test git utility functions."""

    def test_get_current_commit_hash(self):
        """Test getting current commit hash."""
        commit_hash = get_current_commit_hash()

        # Should return a 40-character SHA hash or None if not in git repo
        if commit_hash:
            assert len(commit_hash) == 40
            assert all(c in '0123456789abcdef' for c in commit_hash.lower())

    def test_get_commit_info(self):
        """Test getting commit information."""
        commit_info = get_commit_info()

        # If in git repo, should return commit info
        if commit_info:
            assert 'hash' in commit_info
            assert 'message' in commit_info
            assert 'author' in commit_info
            assert 'email' in commit_info
            # date, branch, and tags are optional


class TestVersionTracking:
    """Test ExtractorVersion tracking in storage."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary test database with required tables."""
        with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as f:
            db_path = f.name

        # Create minimal schema for testing
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # ExtractorVersion table
        cursor.execute("""
            CREATE TABLE app_extractorversion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commit_hash VARCHAR(40) NOT NULL,
                extractor_module VARCHAR(255) NOT NULL,
                commit_message TEXT,
                commit_author VARCHAR(200),
                commit_date DATETIME,
                metadata TEXT,
                created_at DATETIME NOT NULL
            )
        """)

        # Create unique index
        cursor.execute("""
            CREATE UNIQUE INDEX idx_extractor_version_unique
            ON app_extractorversion(commit_hash, extractor_module)
        """)

        # OperationLog table
        cursor.execute("""
            CREATE TABLE app_operationlog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service VARCHAR(50) NOT NULL,
                task_id VARCHAR(100),
                listing_id VARCHAR(32),
                product_id VARCHAR(32),
                level VARCHAR(10) NOT NULL,
                event VARCHAR(100) NOT NULL,
                message TEXT,
                context TEXT,
                filename VARCHAR(100),
                timestamp DATETIME NOT NULL,
                duration_ms INTEGER
            )
        """)

        conn.commit()
        conn.close()

        yield db_path

        # Cleanup
        Path(db_path).unlink()

    def test_get_or_create_extractor_version_new(self, temp_db):
        """Test creating a new extractor version."""
        storage = PriceStorage(temp_db)

        # Get current commit hash (or use a fake one for testing)
        commit_hash = get_current_commit_hash()
        if not commit_hash:
            commit_hash = "0" * 40  # Fake hash for testing outside git repo

        version_id = storage.get_or_create_extractor_version(
            "test_extractor",
            commit_hash=commit_hash
        )

        assert version_id is not None
        assert isinstance(version_id, int)

        # Verify it was saved to database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT commit_hash, extractor_module FROM app_extractorversion WHERE id = ?",
            (version_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == commit_hash
        assert row[1] == "test_extractor"

    def test_get_or_create_extractor_version_existing(self, temp_db):
        """Test getting an existing extractor version."""
        storage = PriceStorage(temp_db)

        commit_hash = "a" * 40  # Fake hash

        # Create first time
        version_id_1 = storage.get_or_create_extractor_version(
            "test_extractor",
            commit_hash=commit_hash
        )

        # Get existing
        version_id_2 = storage.get_or_create_extractor_version(
            "test_extractor",
            commit_hash=commit_hash
        )

        # Should return same ID
        assert version_id_1 == version_id_2

    def test_log_operation(self, temp_db):
        """Test logging an operation."""
        storage = PriceStorage(temp_db)

        storage.log_operation(
            service="fetcher",
            level="INFO",
            event="test_event",
            message="Test message",
            context={"key": "value", "number": 42},
            filename="test.py",
            duration_ms=100
        )

        # Verify it was saved
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT service, level, event, message, context, duration_ms FROM app_operationlog"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "fetcher"
        assert row[1] == "INFO"
        assert row[2] == "test_event"
        assert row[3] == "Test message"

        # Context should be JSON
        context = json.loads(row[4])
        assert context["key"] == "value"
        assert context["number"] == 42
        assert row[5] == 100

    def test_log_operation_with_ids(self, temp_db):
        """Test logging an operation with listing and product IDs."""
        storage = PriceStorage(temp_db)

        listing_id = "12345678-1234-1234-1234-123456789abc"
        product_id = "87654321-4321-4321-4321-cba987654321"

        storage.log_operation(
            service="fetcher",
            level="ERROR",
            event="fetch_failed",
            message="Fetch failed",
            context={"error": "Connection timeout"},
            listing_id=listing_id,
            product_id=product_id,
            filename="fetcher.py",
        )

        # Verify UUIDs were cleaned (hyphens removed)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT listing_id, product_id FROM app_operationlog"
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == listing_id.replace("-", "")
        assert row[1] == product_id.replace("-", "")
