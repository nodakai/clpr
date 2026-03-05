#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick database validation for CI/CD pipelines."""

import sqlite3
import sys
from pathlib import Path


def quick_validate(
    db_path="data/aws_pricing.sqlite3", min_size_bytes=50 * 1024 * 1024, min_rows=1000
):
    """Run quick validation checks suitable for CI.

    Returns:
        bool: True if all checks pass, False otherwise.
    """
    failed = False

    # 1. File exists and minimum size (50MB)
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"FAIL: Database file not found: {db_path}")
        return False

    db_size = db_file.stat().st_size
    if db_size < min_size_bytes:
        print(
            f"FAIL: Database too small: {db_size:,} bytes (expected >= {min_size_bytes:,} bytes)"
        )
        return False
    print(f"PASS: Database size: {db_size:,} bytes")

    # 2. Connect and verify core structure
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'"
            )
            if not cursor.fetchone():
                print("FAIL: Table 'prices' does not exist")
                return False
            print("PASS: Table 'prices' exists")

            # Check required indexes
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices'"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            required_indexes = ["idx_filter", "idx_instance", "idx_price", "idx_specs"]
            missing = [idx for idx in required_indexes if idx not in indexes]
            if missing:
                print(f"FAIL: Missing indexes: {missing}")
                return False
            print(f"PASS: All {len(required_indexes)} indexes present")

            # Row count check
            cursor.execute("SELECT COUNT(*) FROM prices")
            total_rows = cursor.fetchone()[0]
            if total_rows < min_rows:
                print(f"FAIL: Too few rows: {total_rows} (expected >= {min_rows})")
                return False
            print(f"PASS: Total rows: {total_rows:,}")

            # EC2 row count
            cursor.execute("SELECT COUNT(*) FROM prices WHERE service='ec2'")
            ec2_rows = cursor.fetchone()[0]
            if ec2_rows < min_rows:
                print(f"FAIL: Too few EC2 rows: {ec2_rows} (expected >= {min_rows})")
                return False
            print(f"PASS: EC2 rows: {ec2_rows:,}")

            # NULL check on critical columns
            cursor.execute(
                "SELECT COUNT(*) FROM prices WHERE service IS NULL OR region IS NULL OR hourly IS NULL"
            )
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                print(f"FAIL: Found {null_count} rows with NULL in critical columns")
                return False
            print("PASS: No NULLs in critical columns")

            # Service codes check
            cursor.execute("SELECT DISTINCT service FROM prices")
            services = [row[0] for row in cursor.fetchall()]
            expected = ["ec2", "rds", "lambda", "s3"]
            missing_services = [s for s in expected if s not in services]
            if missing_services:
                print(f"FAIL: Missing expected services: {missing_services}")
                return False
            print(f"PASS: All expected services present")

    except sqlite3.Error as e:
        print(f"FAIL: Cannot connect to database: {e}")
        return False

    print("\nAll CI validation checks passed!")
    return True


if __name__ == "__main__":
    success = quick_validate()
    sys.exit(0 if success else 1)
