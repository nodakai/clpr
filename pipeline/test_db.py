#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive database validation for AWS pricing SQLite database."""

import sqlite3
import sys
from pathlib import Path

import click


def format_size(bytes_size):
    """Convert bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def validate_database(
    db_path="data/aws_pricing.sqlite3", min_size_bytes=100 * 1024 * 1024
):
    """Run comprehensive validation checks on the database.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        bool: True if all critical checks pass, False otherwise.
    """
    critical_failed = False
    warnings = []
    results = []

    # 1. Check file exists and size
    db_file = Path(db_path)
    if not db_file.exists():
        click.secho(f"[FAIL] Database file not found: {db_path}", fg="red", bold=True)
        critical_failed = True
        return False
    else:
        db_size = db_file.stat().st_size
        results.append(
            ("Database size", format_size(db_size), db_size > min_size_bytes)
        )
        if db_size > min_size_bytes:
            click.secho(f"[PASS] Database size: {format_size(db_size)}", fg="green")
        else:
            click.secho(
                f"[FAIL] Database size too small: {format_size(db_size)} (expected >{format_size(min_size_bytes)})",
                fg="red",
                bold=True,
            )
            critical_failed = True

    # 2. Connect and verify tables
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            if "prices" in tables:
                click.secho("[PASS] Table 'prices' exists", fg="green")
                results.append(("Table structure", "prices table exists", True))
            else:
                click.secho("[FAIL] Table 'prices' not found", fg="red", bold=True)
                critical_failed = True
                results.append(("Table structure", "prices table missing", False))
    except sqlite3.Error as e:
        click.secho(f"[FAIL] Database connection error: {e}", fg="red", bold=True)
        critical_failed = True
        return False

    # 3. Count rows (total and EC2)
    try:
        cursor.execute("SELECT COUNT(*) FROM prices")
        total_rows = cursor.fetchone()[0]
        results.append(("Total rows", f"{total_rows:,}", total_rows > 0))
        click.secho(f"[PASS] Total rows: {total_rows:,}", fg="green")

        cursor.execute("SELECT COUNT(*) FROM prices WHERE service = 'ec2'")
        ec2_rows = cursor.fetchone()[0]
        if ec2_rows > 5000:
            click.secho(f"[PASS] EC2 rows: {ec2_rows:,} (>5000)", fg="green")
            results.append(("EC2 row count", f"{ec2_rows:,}", True))
        else:
            click.secho(f"[WARN] EC2 rows: {ec2_rows:,} (expected >5000)", fg="yellow")
            warnings.append(f"Low EC2 row count: {ec2_rows}")
            results.append(("EC2 row count", f"{ec2_rows:,}", False))
    except sqlite3.Error as e:
        click.secho(f"[FAIL] Row count query failed: {e}", fg="red", bold=True)
        critical_failed = True

    # 4. Check indexes
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        expected_indexes = ["idx_filter", "idx_instance", "idx_price", "idx_specs"]
        missing = [idx for idx in expected_indexes if idx not in indexes]

        if not missing:
            click.secho("[PASS] All required indexes present", fg="green")
            results.append(
                ("Indexes", f"All {len(expected_indexes)} indexes found", True)
            )
        else:
            click.secho(f"[FAIL] Missing indexes: {missing}", fg="red", bold=True)
            critical_failed = True
            results.append(("Indexes", f"Missing: {missing}", False))
    except sqlite3.Error as e:
        click.secho(f"[FAIL] Index check failed: {e}", fg="red", bold=True)
        critical_failed = True

    # 5. Query plan analysis
    try:
        test_query = "SELECT * FROM prices WHERE service='ec2' AND vcpu >= 4"
        cursor.execute(f"EXPLAIN QUERY PLAN {test_query}")
        plan_rows = cursor.fetchall()
        plan_text = " ".join(str(row) for row in plan_rows)

        uses_index = (
            "USING INDEX" in plan_text.upper() or "IDX_FILTER" in plan_text.upper()
        )
        if uses_index:
            click.secho("[PASS] Query plan uses index (idx_filter)", fg="green")
            results.append(("Query plan", "Uses index", True))
        else:
            click.secho(
                "[WARN] Query plan may use full table scan (check 'SCAN TABLE' in output)",
                fg="yellow",
            )
            warnings.append("Query plan shows full table scan for vcpu filter")
            results.append(("Query plan", "Full scan warning", False))
    except sqlite3.Error as e:
        click.secho(f"[WARN] Query plan analysis failed: {e}", fg="yellow")
        warnings.append(f"Query plan check error: {e}")

    # 6. NULL checks in critical columns
    try:
        null_check_sql = """
        SELECT COUNT(*) FROM prices
        WHERE service IS NULL OR region IS NULL OR hourly IS NULL
        """
        cursor.execute(null_check_sql)
        null_count = cursor.fetchone()[0]
        if null_count == 0:
            click.secho("[PASS] No NULL values in critical columns", fg="green")
            results.append(("NULL check", "0 NULLs in critical columns", True))
        else:
            click.secho(
                f"[FAIL] Found {null_count} rows with NULL in critical columns",
                fg="red",
                bold=True,
            )
            critical_failed = True
            results.append(("NULL check", f"{null_count} NULLs found", False))
    except sqlite3.Error as e:
        click.secho(f"[FAIL] NULL check failed: {e}", fg="red", bold=True)
        critical_failed = True

    # 7. Service codes verification
    try:
        cursor.execute("SELECT DISTINCT service FROM prices ORDER BY service")
        services = [row[0] for row in cursor.fetchall()]
        expected_services = ["ec2", "rds", "lambda", "s3"]
        missing_services = [s for s in expected_services if s not in services]

        if not missing_services:
            click.secho(
                f"[PASS] All expected services present (ec2, rds, lambda, s3)",
                fg="green",
            )
            results.append(("Service codes", "All expected services present", True))
        else:
            click.secho(
                f"[WARN] Missing expected services: {missing_services}", fg="yellow"
            )
            warnings.append(f"Missing services: {missing_services}")
            results.append(("Service codes", f"Missing: {missing_services}", False))
    except sqlite3.Error as e:
        click.secho(f"[FAIL] Service code check failed: {e}", fg="red", bold=True)
        critical_failed = True

    # 8. Reserved pricing upfront_cost check
    try:
        cursor.execute("""
        SELECT COUNT(*) FROM prices
        WHERE purchase_option = 'Reserved' AND upfront_cost IS NOT NULL
        """)
        reserved_with_upfront = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM prices WHERE purchase_option = 'Reserved'")
        total_reserved = cursor.fetchone()[0]

        if total_reserved > 0 and reserved_with_upfront > 0:
            click.secho(
                f"[PASS] Reserved pricing has upfront_cost ({reserved_with_upfront}/{total_reserved} rows)",
                fg="green",
            )
            results.append(
                (
                    "Reserved pricing",
                    f"{reserved_with_upfront}/{total_reserved} have upfront_cost",
                    True,
                )
            )
        elif total_reserved == 0:
            click.secho("[WARN] No Reserved pricing found in database", fg="yellow")
            warnings.append("No Reserved pricing rows")
            results.append(("Reserved pricing", "No Reserved rows", None))
        else:
            click.secho(
                f"[FAIL] Reserved pricing missing upfront_cost", fg="red", bold=True
            )
            critical_failed = True
            results.append(("Reserved pricing", "Missing upfront_cost", False))
    except sqlite3.Error as e:
        click.secho(f"[FAIL] Reserved pricing check failed: {e}", fg="red", bold=True)
        critical_failed = True

    # 9. Monthly/hourly conversion check (monthly ≈ hourly * 730 ±1%)
    try:
        cursor.execute("""
        SELECT COUNT(*) FROM prices
        WHERE hourly IS NOT NULL AND monthly IS NOT NULL
          AND ABS(monthly - (hourly * 730)) / (hourly * 730) > 0.01
        """)
        conversion_errors = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM prices WHERE hourly IS NOT NULL AND monthly IS NOT NULL"
        )
        total_conversion_check = cursor.fetchone()[0]

        if total_conversion_check > 0 and conversion_errors == 0:
            click.secho("[PASS] Monthly/hourly conversion within 1%", fg="green")
            results.append(("Monthly conversion", "Within 1% tolerance", True))
        elif total_conversion_check == 0:
            click.secho(
                "[WARN] No rows with both hourly and monthly for conversion check",
                fg="yellow",
            )
            warnings.append("No conversion check data")
            results.append(("Monthly conversion", "No data", None))
        else:
            error_pct = (conversion_errors / total_conversion_check) * 100
            click.secho(
                f"[WARN] {conversion_errors}/{total_conversion_check} rows ({error_pct:.1f}%) outside 1% tolerance",
                fg="yellow",
            )
            warnings.append(
                f"Conversion errors: {conversion_errors}/{total_conversion_check}"
            )
            results.append(
                ("Monthly conversion", f"{error_pct:.1f}% outside tolerance", False)
            )
    except sqlite3.Error as e:
        click.secho(f"[WARN] Conversion check failed: {e}", fg="yellow")
        warnings.append(f"Conversion check error: {e}")

    # Summary
    click.echo("\n" + "=" * 60)
    click.secho("VALIDATION SUMMARY", fg="cyan", bold=True)
    click.echo("=" * 60)

    passed = sum(1 for _, _, result in results if result is True)
    failed = sum(1 for _, _, result in results if result is False)
    warn_count = sum(1 for _, _, result in results if result is None) + len(warnings)

    for check_name, detail, result in results:
        if result is True:
            click.secho(f"[PASS] {check_name}: {detail}", fg="green")
        elif result is False:
            click.secho(f"[FAIL] {check_name}: {detail}", fg="red", bold=True)
        else:
            click.secho(f"[WARN] {check_name}: {detail}", fg="yellow")

    if warnings:
        click.echo("\nWarnings:")
        for w in warnings:
            click.secho(f"  • {w}", fg="yellow")

    click.echo("=" * 60)
    click.secho(
        f"Results: {passed} passed, {failed} failed, {len(warnings)} warnings",
        fg="cyan",
    )

    if critical_failed:
        click.secho("\nCRITICAL VALIDATION FAILED", fg="red", bold=True, bg="white")
        return False
    else:
        click.secho("\nAll critical checks passed", fg="green", bold=True)
        return True


@click.command()
@click.option(
    "--db-path", default="data/aws_pricing.sqlite3", help="Path to database file"
)
@click.option(
    "--min-size",
    default=100 * 1024 * 1024,
    type=int,
    help="Minimum size in bytes (default 100MB)",
)
def main(db_path, min_size):
    """Validate AWS pricing database structure and integrity."""
    success = validate_database(db_path, min_size_bytes=min_size)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
