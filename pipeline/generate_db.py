"""Database generation and optimization module.

This module orchestrates the normalization of AWS pricing data and creates
an optimized SQLite database with appropriate indexes and settings.
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path

from pipeline.schema import initialize_database, PriceRow
from pipeline.normalize import normalize_all

logger = logging.getLogger(__name__)


def generate_database(
    output_path: str | Path = "data/aws_pricing.sqlite3",
    max_size_bytes: int = 500 * 1024 * 1024,
    min_rows: int = 1000,
) -> None:
    """Generate final optimized SQLite database.

    Args:
        output_path: Path where the SQLite database will be created.
                     Defaults to 'data/aws_pricing.sqlite3'.
        max_size_bytes: Maximum allowed database size in bytes.
                       Defaults to 500 MB.
        min_rows: Minimum required rows in prices table.
                 Defaults to 1000.
    """
    output_path = Path(output_path)

    # a. Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Generating database at: {output_path}")

    # b. Call normalize_all() to populate database
    logger.info("Normalizing data and populating database...")
    normalize_all(output_path)
    logger.info("Normalization completed.")

    # c. After normalization, run optimizations
    logger.info("Running database optimizations...")
    with sqlite3.connect(output_path) as conn:
        # VACUUM to defragment and minimize file size
        logger.info("Running VACUUM...")
        conn.execute("VACUUM;")

        # ANALYZE to gather statistics for query planner
        logger.info("Running ANALYZE...")
        conn.execute("ANALYZE;")

        # Verify indexes exist
        logger.info("Verifying indexes...")
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices';"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        expected_indexes = ["idx_filter", "idx_instance", "idx_price", "idx_specs"]
        missing_indexes = [idx for idx in expected_indexes if idx not in indexes]
        if missing_indexes:
            logger.error(f"Missing indexes: {missing_indexes}")
            raise SystemExit(f"Index creation failed: missing {missing_indexes}")
        logger.info(f"All {len(expected_indexes)} indexes verified.")

    # d. Print summary
    logger.info("Generating summary...")

    # Database file size
    db_size_bytes = os.path.getsize(str(output_path))
    db_size_mb = db_size_bytes / (1024 * 1024)
    logger.info(f"Database file size: {db_size_mb:.2f} MB")

    with sqlite3.connect(output_path) as conn:
        # Total rows
        cursor = conn.execute("SELECT COUNT(*) FROM prices;")
        total_rows = cursor.fetchone()[0]
        logger.info(f"Total rows in prices table: {total_rows}")

        # Breakdown by service
        cursor = conn.execute(
            "SELECT service, COUNT(*) FROM prices GROUP BY service ORDER BY COUNT(*) DESC;"
        )
        service_breakdown = cursor.fetchall()
        logger.info("Breakdown by service:")
        for service, count in service_breakdown:
            logger.info(f"  {service}: {count}")

        # Number of distinct regions
        cursor = conn.execute("SELECT COUNT(DISTINCT region) FROM prices;")
        region_count = cursor.fetchone()[0]
        logger.info(f"Number of distinct regions: {region_count}")

        # Query plan check on sample query
        sample_query = "SELECT * FROM prices WHERE service='ec2' AND vcpu >= 4;"
        cursor = conn.execute(f"EXPLAIN QUERY PLAN {sample_query}")
        plan_rows = cursor.fetchall()
        plan_text = " | ".join(" ".join(str(col) for col in row) for row in plan_rows)
        logger.debug(f"Query plan: {plan_text}")
        if "idx_filter" in plan_text or "USING INDEX" in plan_text:
            logger.info("Query plan indicates index usage for sample query.")
        else:
            logger.warning(
                "Query plan does NOT show index usage for sample query. Check indexes."
            )

    # 4. Validation
    if max_size_bytes > 0 and db_size_bytes >= max_size_bytes:
        raise SystemExit(
            f"Validation failed: Database size {db_size_mb:.2f} MB >= {max_size_bytes / (1024 * 1024):.0f} MB"
        )
    if min_rows > 0 and total_rows < min_rows:
        raise SystemExit(
            f"Validation failed: Only {total_rows} rows (expected >= {min_rows})"
        )
    if total_rows < min_rows:
        raise SystemExit(
            f"Validation failed: Only {total_rows} rows (expected >= {min_rows})"
        )

    # 5. Optional .dbi helper file
    dbi_path = output_path.with_suffix(".dbi")
    dbi_path.write_text("{}")
    logger.info(f"Created .dbi file: {dbi_path}")

    logger.info("Database generation and validation completed successfully!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    generate_database()
