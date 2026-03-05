"""Database schema definitions for AWS pricing data.

This module defines the flattened prices table schema and provides functions
to create the table and indexes in a SQLite database.
"""

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass
class PriceRow:
    """Represents a single row in the prices table."""

    id: Optional[int] = None
    service: Optional[str] = None
    region: Optional[str] = None
    instance_type: Optional[str] = None
    family: Optional[str] = None
    size: Optional[str] = None
    vcpu: Optional[int] = None
    memory_gb: Optional[float] = None
    storage: Optional[str] = None
    storage_gb: Optional[int] = None
    storage_type: Optional[str] = None
    network_performance: Optional[str] = None
    processor: Optional[str] = None
    burst_capable: Optional[bool] = None
    gpu: Optional[int] = 0
    gpu_memory_gb: Optional[float] = None
    os: Optional[str] = None
    tenancy: Optional[str] = None
    price_unit: Optional[str] = None
    purchase_option: Optional[str] = None
    lease_term: Optional[str] = None
    purchase_option_reserved: Optional[str] = None
    offering_class: Optional[str] = None
    hourly: Optional[float] = None
    monthly: Optional[float] = None
    upfront_cost: Optional[float] = None
    effective_date: Optional[str] = None
    sku: Optional[str] = None
    rate_code: Optional[str] = None


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    region TEXT NOT NULL,
    instance_type TEXT,
    family TEXT,
    size TEXT,
    vcpu INTEGER,
    memory_gb REAL,
    storage TEXT,
    storage_gb INTEGER,
    storage_type TEXT,
    network_performance TEXT,
    processor TEXT,
    burst_capable BOOLEAN DEFAULT 0,
    gpu INTEGER DEFAULT 0,
    gpu_memory_gb REAL,
    os TEXT NOT NULL,
    tenancy TEXT,
    price_unit TEXT,
    purchase_option TEXT NOT NULL,
    lease_term TEXT,
    purchase_option_reserved TEXT,
    offering_class TEXT,
    hourly REAL NOT NULL,
    monthly REAL,
    upfront_cost REAL,
    effective_date TEXT,
    sku TEXT,
    rate_code TEXT,
    UNIQUE(service, region, instance_type, os, tenancy, purchase_option, lease_term, purchase_option_reserved, offering_class)
);
"""


CREATE_INDEX_SQLS = [
    """CREATE INDEX IF NOT EXISTS idx_filter ON prices(service, region, os, tenancy, vcpu, hourly);""",
    """CREATE INDEX IF NOT EXISTS idx_instance ON prices(service, instance_type);""",
    """CREATE INDEX IF NOT EXISTS idx_price ON prices(service, region, purchase_option, hourly);""",
    """CREATE INDEX IF NOT EXISTS idx_specs ON prices(vcpu, memory_gb, storage_type);""",
]

PRAGMA_SETTINGS = [
    "PRAGMA page_size = 1024",
    "PRAGMA journal_mode = WAL",
    "PRAGMA foreign_keys = ON",
]


def create_tables(conn: sqlite3.Connection) -> None:
    """Create the prices table if it does not exist.

    Executes the CREATE TABLE statement with proper SQLite syntax.
    The table structure is defined by CREATE_TABLE_SQL constant.

    Args:
        conn: SQLite database connection.
    """
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes on the prices table for query optimization.

    Creates the following indexes:
    - idx_filter: for filtering by service, region, os, tenancy, vcpu, hourly
    - idx_instance: for looking up specific instance types
    - idx_price: for price-based queries across service/region/purchase_option
    - idx_specs: for filtering by hardware specifications

    Args:
        conn: SQLite database connection.
    """
    for sql in CREATE_INDEX_SQLS:
        conn.execute(sql)
    conn.commit()


def set_pragmas(conn: sqlite3.Connection) -> None:
    """Configure SQLite pragmas for optimal performance and consistency.

    Sets:
    - page_size=1024: Optimized for HTTP Range requests (must be set before DB creation)
    - journal_mode=WAL: Write-Ahead Logging for better concurrency
    - foreign_keys=ON: Enforce foreign key constraints

    Args:
        conn: SQLite database connection.
    """
    for pragma in PRAGMA_SETTINGS:
        conn.execute(pragma)
    conn.commit()


def initialize_database(conn: sqlite3.Connection) -> None:
    """Initialize the database with tables, indexes, and pragma settings.

    This convenience function calls create_tables(), create_indexes(),
    and set_pragmas() in the proper order.

     Note: page_size must be set before creating any tables for it to take effect.
     If the table already exists, changing page_size has no effect.

    Args:
        conn: SQLite database connection.
    """
    set_pragmas(conn)
    create_tables(conn)
    create_indexes(conn)


if __name__ == "__main__":
    # Simple test: create in-memory database and verify schema
    with sqlite3.connect(":memory:") as connection:
        initialize_database(connection)

        # Verify table exists
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prices';"
        )
        result = cursor.fetchone()
        assert result is not None, "prices table was not created"
        print("✓ prices table created")

        # Verify indexes exist
        cursor = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices';"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        expected_indexes = ["idx_filter", "idx_instance", "idx_price", "idx_specs"]
        for idx in expected_indexes:
            assert idx in indexes, f"Index {idx} was not created"
        print(f"✓ {len(expected_indexes)} indexes created")

        # Verify pragma settings
        cursor = connection.execute("PRAGMA page_size;")
        page_size = cursor.fetchone()[0]
        assert page_size == 1024, f"page_size is {page_size}, expected 1024"
        print("✓ page_size = 1024")

        cursor = connection.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        # In-memory databases may return 'memory' instead of 'wal'
        assert journal_mode.upper() in ("WAL", "MEMORY"), (
            f"journal_mode is {journal_mode}, expected WAL or MEMORY"
        )
        print(f"✓ journal_mode = {journal_mode.upper()}")

        cursor = connection.execute("PRAGMA foreign_keys;")
        foreign_keys = cursor.fetchone()[0]
        assert foreign_keys == 1, f"foreign_keys is {foreign_keys}, expected 1"
        print("✓ foreign_keys = ON")

        print("\nAll schema tests passed✓")
