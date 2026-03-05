"""Unit tests for pipeline.schema module."""

import sqlite3
import pytest
from pipeline.schema import (
    PriceRow,
    create_tables,
    create_indexes,
    set_pragmas,
    initialize_database,
    CREATE_TABLE_SQL,
    CREATE_INDEX_SQLS,
    PRAGMA_SETTINGS,
)


class TestPriceRow:
    """Test PriceRow dataclass."""

    def test_creation_with_defaults(self):
        """Test creating PriceRow with default values."""
        row = PriceRow()
        assert row.id is None
        assert row.service is None
        assert row.region is None
        assert row.vcpu is None
        assert row.memory_gb is None
        assert row.gpu == 0  # Default is 0 per schema
        assert row.burst_capable is None

    def test_creation_with_values(self):
        """Test creating PriceRow with explicit values."""
        row = PriceRow(
            service="ec2",
            region="us-east-1",
            instance_type="m5.large",
            vcpu=2,
            memory_gb=8.0,
            hourly=0.096,
            purchase_option="OnDemand",
        )
        assert row.service == "ec2"
        assert row.region == "us-east-1"
        assert row.instance_type == "m5.large"
        assert row.vcpu == 2
        assert row.memory_gb == 8.0
        assert row.hourly == 0.096
        assert row.purchase_option == "OnDemand"


class TestCreateTables:
    """Test create_tables function."""

    def test_creates_prices_table(self):
        """Test that create_tables creates the prices table."""
        with sqlite3.connect(":memory:") as conn:
            create_tables(conn)

            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='prices';"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "prices"

    def test_table_has_required_columns(self):
        """Test that the prices table has all expected columns."""
        with sqlite3.connect(":memory:") as conn:
            create_tables(conn)

            cursor = conn.execute("PRAGMA table_info(prices);")
            columns = {row[1] for row in cursor.fetchall()}

            expected_columns = {
                "id",
                "service",
                "region",
                "instance_type",
                "family",
                "size",
                "vcpu",
                "memory_gb",
                "storage",
                "storage_gb",
                "storage_type",
                "network_performance",
                "processor",
                "burst_capable",
                "gpu",
                "gpu_memory_gb",
                "os",
                "tenancy",
                "price_unit",
                "purchase_option",
                "lease_term",
                "purchase_option_reserved",
                "offering_class",
                "hourly",
                "monthly",
                "upfront_cost",
                "effective_date",
                "sku",
                "rate_code",
            }
            assert expected_columns.issubset(columns)

    def test_unique_constraint_exists(self):
        """Test that the unique constraint is defined in the table schema."""
        with sqlite3.connect(":memory:") as conn:
            create_tables(conn)

            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='prices';"
            )
            table_sql = cursor.fetchone()[0]

            # Check that UNIQUE constraint includes the expected fields
            assert "UNIQUE" in table_sql.upper()
            assert "service" in table_sql
            assert "region" in table_sql
            assert "instance_type" in table_sql

    def test_table_not_overwritten_if_exists(self):
        """Test that CREATE TABLE IF NOT EXISTS doesn't fail on existing table."""
        with sqlite3.connect(":memory:") as conn:
            create_tables(conn)
            create_tables(conn)  # Should not raise an error


class TestCreateIndexes:
    """Test create_indexes function."""

    def test_creates_all_indexes(self):
        """Test that all expected indexes are created."""
        with sqlite3.connect(":memory:") as conn:
            create_tables(conn)
            create_indexes(conn)

            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices';"
            )
            indexes = {row[0] for row in cursor.fetchall()}

            expected_indexes = {"idx_filter", "idx_instance", "idx_price", "idx_specs"}
            assert expected_indexes.issubset(indexes)

    def test_indexes_on_correct_columns(self):
        """Test that indexes are on the expected columns."""
        with sqlite3.connect(":memory:") as conn:
            create_tables(conn)
            create_indexes(conn)

            cursor = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='prices';"
            )
            index_sql = {row[0]: row[1] for row in cursor.fetchall()}

            # Verify idx_filter covers filter columns
            assert "service" in index_sql["idx_filter"]
            assert "region" in index_sql["idx_filter"]
            assert "os" in index_sql["idx_filter"]
            assert "vcpu" in index_sql["idx_filter"]

            # Verify idx_instance covers service and instance_type
            assert "service" in index_sql["idx_instance"]
            assert "instance_type" in index_sql["idx_instance"]

            # Verify idx_price covers price-related columns
            assert "hourly" in index_sql["idx_price"]

            # Verify idx_specs covers specs
            assert "memory_gb" in index_sql["idx_specs"]

    def test_indexes_not_overwritten_if_exists(self):
        """Test that CREATE INDEX IF NOT EXISTS doesn't fail on existing indexes."""
        with sqlite3.connect(":memory:") as conn:
            create_tables(conn)
            create_indexes(conn)
            create_indexes(conn)  # Should not raise an error


class TestSetPragmas:
    """Test set_pragmas function."""

    def test_sets_page_size(self):
        """Test that page_size pragma is set to 1024."""
        with sqlite3.connect(":memory:") as conn:
            set_pragmas(conn)

            cursor = conn.execute("PRAGMA page_size;")
            page_size = cursor.fetchone()[0]
            assert page_size == 1024

    def test_sets_journal_mode(self):
        """Test that journal_mode is set to WAL."""
        with sqlite3.connect(":memory:") as conn:
            set_pragmas(conn)

            cursor = conn.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            # In-memory databases may return 'memory' instead of 'wal'
            assert journal_mode.upper() in ("WAL", "MEMORY")

    def test_sets_foreign_keys(self):
        """Test that foreign_keys pragma is set to ON."""
        with sqlite3.connect(":memory:") as conn:
            set_pragmas(conn)

            cursor = conn.execute("PRAGMA foreign_keys;")
            foreign_keys = cursor.fetchone()[0]
            assert foreign_keys == 1

    def test_all_pragmas_are_set(self):
        """Test that all expected pragmas are in PRAGMA_SETTINGS."""
        expected_pragmas = {
            "PRAGMA page_size = 1024",
            "PRAGMA journal_mode = WAL",
            "PRAGMA foreign_keys = ON",
        }
        actual_pragmas = set(PRAGMA_SETTINGS)
        assert expected_pragmas.issubset(actual_pragmas)


class TestInitializeDatabase:
    """Test initialize_database function."""

    def test_initializes_complete_schema(self):
        """Test that initialize_database sets up everything correctly."""
        with sqlite3.connect(":memory:") as conn:
            initialize_database(conn)

            # Verify table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='prices';"
            )
            assert cursor.fetchone() is not None

            # Verify indexes exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices';"
            )
            indexes = {row[0] for row in cursor.fetchall()}
            expected_indexes = {"idx_filter", "idx_instance", "idx_price", "idx_specs"}
            assert expected_indexes.issubset(indexes)

            # Verify pragmas
            cursor = conn.execute("PRAGMA page_size;")
            assert cursor.fetchone()[0] == 1024

            cursor = conn.execute("PRAGMA foreign_keys;")
            assert cursor.fetchone()[0] == 1

    def test_initialize_with_existing_db(self):
        """Test that initialize_database works with existing DB file."""
        with sqlite3.connect(":memory:") as conn:
            initialize_database(conn)
            initialize_database(conn)  # Should not raise error


class TestSchemaConstants:
    """Test schema module constants."""

    def test_create_table_sql_structure(self):
        """Test CREATE_TABLE_SQL has proper structure."""
        assert "CREATE TABLE" in CREATE_TABLE_SQL
        assert "prices" in CREATE_TABLE_SQL
        assert "id INTEGER PRIMARY KEY AUTOINCREMENT" in CREATE_TABLE_SQL
        assert "UNIQUE" in CREATE_TABLE_SQL

    def test_create_index_sqls_non_empty(self):
        """Test CREATE_INDEX_SQLS contains SQL statements."""
        assert len(CREATE_INDEX_SQLS) == 4
        for sql in CREATE_INDEX_SQLS:
            assert "CREATE INDEX" in sql
            assert "prices" in sql

    def test_pragma_settings_non_empty(self):
        """Test PRAGMA_SETTINGS contains settings."""
        assert len(PRAGMA_SETTINGS) == 3
