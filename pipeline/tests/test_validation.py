#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for database validation functions."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

import pytest

from pipeline.schema import initialize_database, create_indexes
from pipeline.validate import quick_validate
from pipeline.test_db import validate_database, main as test_db_main


@pytest.fixture
def temp_valid_db(tmp_path):
    """Create a minimal but valid pricing database."""
    db_path = tmp_path / "valid.db"
    with sqlite3.connect(db_path) as conn:
        initialize_database(conn)
        conn.executemany(
            """
            INSERT INTO prices (service, region, instance_type, os, tenancy, vcpu, memory_gb, hourly, purchase_option)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                (
                    "ec2",
                    "us-east-1",
                    "m5.large",
                    "Linux",
                    "Shared",
                    2,
                    8.0,
                    0.096,
                    "OnDemand",
                ),
                (
                    "ec2",
                    "us-west-1",
                    "t2.micro",
                    "Linux",
                    "Shared",
                    1,
                    1.0,
                    0.012,
                    "OnDemand",
                ),
                (
                    "rds",
                    "us-east-1",
                    "db.t3.medium",
                    "Linux",
                    "Shared",
                    2,
                    4.0,
                    0.05,
                    "OnDemand",
                ),
                (
                    "lambda",
                    "us-east-1",
                    "x86_64",
                    "Linux",
                    "Shared",
                    None,
                    None,
                    0.0000166667,
                    "OnDemand",
                ),
                (
                    "s3",
                    "us-east-1",
                    "Standard",
                    "Standard",
                    None,
                    None,
                    None,
                    0.023,
                    "OnDemand",
                ),
            ],
        )
    return db_path


@pytest.fixture
def temp_db_with_reserved(tmp_path):
    """Create database with reserved pricing."""
    db_path = tmp_path / "reserved.db"
    with sqlite3.connect(db_path) as conn:
        initialize_database(conn)
        conn.executemany(
            """
            INSERT INTO prices (service, region, instance_type, os, tenancy, vcpu, memory_gb, hourly, purchase_option, lease_term, upfront_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                (
                    "ec2",
                    "us-east-1",
                    "m5.large",
                    "Linux",
                    "Shared",
                    2,
                    8.0,
                    0.0,
                    "Reserved",
                    "1yr",
                    200.0,
                ),
                (
                    "ec2",
                    "us-east-1",
                    "m5.xlarge",
                    "Linux",
                    "Shared",
                    4,
                    16.0,
                    0.0,
                    "Reserved",
                    "1yr",
                    400.0,
                ),
            ],
        )
    return db_path


class TestQuickValidate:
    """Tests for pipeline.validate.quick_validate."""

    def test_quick_validate_success(self, temp_valid_db):
        """Valid database passes all checks."""
        assert quick_validate(str(temp_valid_db), min_size_bytes=0, min_rows=0) is True

    def test_quick_validate_missing_file(self, tmp_path):
        """Non-existent file fails."""
        fake_path = tmp_path / "nonexistent.db"
        assert quick_validate(str(fake_path)) is False

    def test_quick_validate_too_small(self, tmp_path):
        """Database smaller than 50MB fails size check."""
        # Create a tiny database
        db_path = tmp_path / "tiny.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
        # The file will be < 50MB
        assert quick_validate(str(db_path)) is False

    def test_quick_validate_missing_table(self, tmp_path):
        """Database without prices table fails."""
        db_path = tmp_path / "no_table.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE other (id INTEGER)")
        assert quick_validate(str(db_path)) is False

    def test_quick_validate_missing_indexes(self, tmp_path):
        """Database missing required indexes fails."""
        db_path = tmp_path / "no_index.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            # Drop some indexes to simulate missing
            conn.execute("DROP INDEX idx_filter")
            conn.execute("DROP INDEX idx_price")
            conn.execute("DROP INDEX idx_specs")
        assert quick_validate(str(db_path)) is False

    def test_quick_validate_too_few_rows(self, tmp_path):
        """Database with less than 1000 rows fails."""
        db_path = tmp_path / "few_rows.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            conn.execute(
                "INSERT INTO prices (service, region, os, purchase_option, hourly) VALUES ('ec2', 'us-east-1', 'Linux', 'OnDemand', 0.096)"
            )
        assert quick_validate(str(db_path)) is False

    def test_quick_validate_insufficient_ec2_rows(self, tmp_path):
        """Database with less than 1000 EC2 rows fails."""
        db_path = tmp_path / "few_ec2.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            # Insert non-ec2 rows
            conn.execute(
                "INSERT INTO prices (service, region, os, purchase_option, hourly) VALUES ('s3', 'us-east-1', 'Standard', 'OnDemand', 0.023)"
            )
        assert quick_validate(str(db_path)) is False

    def test_quick_validate_null_critical_columns(self, tmp_path):
        """Rows with NULL in critical columns fail."""
        pytest.skip("Schema enforces NOT NULL on critical columns, test redundant")

    def test_quick_validate_missing_services(self, tmp_path):
        """Missing expected services fails."""
        db_path = tmp_path / "one_service.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            conn.execute(
                "INSERT INTO prices (service, region, os, purchase_option, hourly) VALUES ('ec2', 'us-east-1', 'Linux', 'OnDemand', 0.096)"
            )
        assert quick_validate(str(db_path)) is False


class TestValidateDatabase:
    """Tests for pipeline.test_db.validate_database."""

    def test_validate_database_success(self, temp_valid_db):
        """Valid database passes critical checks."""
        assert validate_database(str(temp_valid_db), min_size_bytes=0) is True

    def test_validate_database_custom_db_path(self, temp_valid_db):
        """Custom path works."""
        assert validate_database(str(temp_valid_db), min_size_bytes=0) is True

    def test_validate_database_missing_file(self, tmp_path):
        """Non-existent file results in critical failure."""
        fake_path = tmp_path / "nonexistent.db"
        assert validate_database(str(fake_path)) is False

    def test_validate_database_too_small(self, tmp_path):
        """Database smaller than 100MB fails."""
        db_path = tmp_path / "tiny.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
        assert validate_database(str(db_path)) is False

    def test_validate_database_missing_prices_table(self, tmp_path):
        """Database without prices table fails."""
        db_path = tmp_path / "no_prices.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE other (id INTEGER)")
        assert validate_database(str(db_path)) is False

    def test_validate_database_missing_all_indexes(self, tmp_path):
        """Database with no indexes fails."""
        db_path = tmp_path / "no_indexes.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            # Drop all indexes (they're created in initialize_database, so we need to remove them)
            cursor = conn.cursor()
            cursor.execute("DROP INDEX IF EXISTS idx_filter")
            cursor.execute("DROP INDEX IF EXISTS idx_instance")
            cursor.execute("DROP INDEX IF EXISTS idx_price")
            cursor.execute("DROP INDEX IF EXISTS idx_specs")
        assert validate_database(str(db_path)) is False

    def test_validate_database_missing_one_index(self, tmp_path):
        """Missing one required index fails."""
        db_path = tmp_path / "partial_indexes.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            # Drop one index
            conn.execute("DROP INDEX IF EXISTS idx_price")
        assert validate_database(str(db_path)) is False

    def test_validate_database_reserved_pricing_upfront_cost(
        self, temp_db_with_reserved
    ):
        """Reserved pricing with upfront_cost passes."""
        assert validate_database(str(temp_db_with_reserved), min_size_bytes=0) is True

    def test_validate_database_reserved_missing_upfront_cost(self, tmp_path):
        """Reserved pricing without upfront_cost fails."""
        db_path = tmp_path / "reserved_no_upfront.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            conn.execute("""
                INSERT INTO prices (service, region, os, purchase_option, hourly, lease_term, upfront_cost)
                VALUES ('ec2', 'us-east-1', 'Linux', 'Reserved', 0.0, '1yr', NULL)
            """)
        assert validate_database(str(db_path)) is False

    def test_validate_database_monthly_conversion_error(self, tmp_path):
        """Rows with bad monthly/hourly conversion trigger warning but not critical failure."""
        db_path = tmp_path / "bad_conversion.db"
        with sqlite3.connect(db_path) as conn:
            initialize_database(conn)
            # Insert rows with bad conversion: monthly should be ~hourly * 730
            conn.execute("""
                INSERT INTO prices (service, region, os, purchase_option, hourly, monthly)
                VALUES ('ec2', 'us-east-1', 'Linux', 'OnDemand', 1.0, 999.0)  -- Way off
            """)
        # This should return True (warnings only) since there's still valid data
        assert validate_database(str(db_path), min_size_bytes=0) is True

    def test_validate_database_null_in_critical_columns(self, tmp_path):
        """Rows with NULL in service/region/hourly fail."""
        pytest.skip("Schema enforces NOT NULL on critical columns, test redundant")


class TestTestDbMain:
    """Tests for pipeline.test_db.main (CLI entry point)."""

    def test_main_success(self, temp_valid_db, capsys, mocker):
        """main() exits with 0 on success."""
        # Ensure we don't actually call sys.exit in the test runner
        mocker.patch(
            "sys.argv",
            ["test_db.py", "--db-path", str(temp_valid_db), "--min-size", "0"],
        )
        try:
            test_db_main()
        except SystemExit as e:
            assert e.code == 0
        captured = capsys.readouterr()
        assert "VALIDATION" in captured.out or "validation" in captured.out.lower()

    def test_main_failure(self, tmp_path, capsys, mocker):
        """main() exits with 1 on failure."""
        db_path = tmp_path / "bad.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE other (id INTEGER)")
        mocker.patch("sys.argv", ["test_db.py", "--db-path", str(db_path)])
        try:
            test_db_main()
        except SystemExit as e:
            assert e.code == 1
        captured = capsys.readouterr()
        assert "CRITICAL" in captured.out or "FAIL" in captured.out

    def test_main_uses_default_path_when_not_specified(self, mocker, tmp_path):
        """main() uses default data/aws_pricing.sqlite3 when no arg given."""
        # Create a minimal valid db at the default path location
        default_path = Path("data/aws_pricing.sqlite3")
        if default_path.exists():
            # Skip if real DB exists
            pytest.skip("Default database already exists")

        # We'll not actually test this without mocking the path creation
        # Just verify the default argument is set correctly
        from pipeline.test_db import main

        # The click decorator sets the default; we can't easily test without click testing
        mocker.patch("sys.argv", ["test_db.py"])
        # This would attempt to load real DB - just skip actual execution
        pytest.skip("CLI default path test requires integration")

    class TestSchemaIntegration:
        """Integration tests using schema functions."""

        def test_schema_initialization_creates_valid_db(self, tmp_path):
            """initialize_database creates all tables and indexes."""
            db_path = tmp_path / "fresh.db"
            with sqlite3.connect(db_path) as conn:
                initialize_database(conn)

                # Check table exists
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'"
                )
                assert cursor.fetchone() is not None

                # Check indexes
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices'"
                )
                indexes = [row[0] for row in cursor.fetchall()]
                expected = ["idx_filter", "idx_instance", "idx_price", "idx_specs"]
                for idx in expected:
                    assert idx in indexes, f"Missing index: {idx}"
