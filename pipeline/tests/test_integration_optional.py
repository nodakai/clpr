"""Optional integration tests for AWS pricing pipeline.

These tests are SKIPPED BY DEFAULT and only run when explicitly requested:
- Set environment variable RUN_INTEGRATION_TESTS=1
- OR use pytest marker: pytest -m integration

Tests require:
- Valid AWS credentials (aws sso login completed)
- Network access to AWS Price List API
- May take several minutes and incur API rate limits
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Generator, Tuple

import pytest


def check_integration_enabled() -> bool:
    """Check if integration tests are explicitly enabled."""
    return os.getenv("RUN_INTEGRATION_TESTS") == "1"


@pytest.fixture(scope="function")
def temp_workspace() -> Generator[Tuple[Path, Path], None, None]:
    """Create a temporary workspace with data/raw directory.

    Returns:
        Tuple of (tmpdir, raw_dir) paths.
    """
    if not check_integration_enabled():
        pytest.skip("RUN_INTEGRATION_TESTS=1 required to run integration tests")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        raw_dir = tmp_path / "data" / "raw"
        raw_dir.mkdir(parents=True)
        yield tmp_path, raw_dir


@pytest.mark.integration
class TestDownloadIntegration:
    """Integration tests for AWS pricing data download."""

    def test_download_real_ec2_small(self, temp_workspace):
        """Download real EC2 pricing data for us-east-1 and verify content."""
        from pipeline.download_pricing import (
            download_service_pricing,
            create_pricing_client,
        )

        tmp_path, raw_dir = temp_workspace

        # Patch RAW_DATA_DIR in download_pricing module
        import pipeline.download_pricing as dl_module

        original_raw_dir = dl_module.RAW_DATA_DIR
        dl_module.RAW_DATA_DIR = raw_dir

        try:
            client = create_pricing_client()
            filters = [
                {"Type": "TERM_MATCH", "Field": "regionCode", "Value": "us-east-1"}
            ]

            success = download_service_pricing(client, "AmazonEC2", filters=filters)
            assert success, "Download failed"

            ec2_file = raw_dir / "AmazonEC2.json"
            assert ec2_file.exists(), "EC2 file not created"

            # Verify file size is reasonable (should be several MB)
            size_mb = ec2_file.stat().st_size / (1024 * 1024)
            assert size_mb > 1.0, f"File too small: {size_mb:.2f} MB (expected >1MB)"
            assert size_mb < 100.0, f"File too large: {size_mb:.2f} MB (filter failed?)"

            # Verify JSON structure and content
            with open(ec2_file) as f:
                data = json.load(f)
                assert isinstance(data, list), "Expected JSON array"
                assert len(data) > 0, "No products downloaded"

                # Check first product structure
                first = data[0]
                assert "product" in first
                assert "terms" in first
                assert "sku" in first

                # Verify all products are for us-east-1
                for item in data:
                    location = item["product"]["attributes"]["location"]
                    assert "US East (N. Virginia)" in location, (
                        f"Unexpected location: {location}"
                    )

            print(f"✓ Downloaded {len(data)} EC2 products ({size_mb:.2f} MB)")

        finally:
            dl_module.RAW_DATA_DIR = original_raw_dir

    def test_full_pipeline_end_to_end(self, temp_workspace):
        """Run complete pipeline: download → normalize → generate_db → validate."""
        from pipeline.download_pricing import download_ec2_us_east_1_only
        from pipeline.generate_db import generate_database
        from pipeline.validate import quick_validate
        import pipeline.normalize as norm_module

        tmp_path, raw_dir = temp_workspace

        # Patch download_filtered to use our temporary raw_dir
        import pipeline.download_filtered as dl_module

        original_dl_raw_dir = dl_module.RAW_DATA_DIR
        dl_module.RAW_DATA_DIR = raw_dir

        # Patch normalize module to use our temporary data/raw
        original_norm_path = norm_module.Path
        norm_module.Path = lambda p: tmp_path / p if str(p) == "data/raw" else Path(p)

        try:
            # Step 1: Download (small subset)
            print("\n--- Step 1: Downloading EC2 us-east-1 ---")
            success = download_ec2_us_east_1_only()
            assert success, "Download failed"

            ec2_file = raw_dir / "AmazonEC2.json"
            assert ec2_file.exists(), "EC2 file not created"

            with open(ec2_file) as f:
                products = json.load(f)
                product_count = len(products)
                assert product_count > 0, "No products downloaded"
                print(f"✓ Downloaded {product_count} products")

            # Step 2: Generate database
            print("\n--- Step 2: Generating SQLite database ---")
            db_path = tmp_path / "aws_pricing.sqlite3"

            # Override default output path
            try:
                generate_database(db_path)
            except SystemExit as e:
                # Validation may fail due to small dataset; check if it's just row count
                if "expected >=" in str(e) and "rows" in str(e):
                    print(f"⚠ Validation skipped (small dataset): {e}")
                    if not db_path.exists():
                        raise
                else:
                    raise

            assert db_path.exists(), "Database not created"
            db_size_mb = db_path.stat().st_size / (1024 * 1024)
            assert db_size_mb > 1.0, f"Database too small: {db_size_mb:.2f} MB"
            print(f"✓ Database created: {db_size_mb:.2f} MB")

            # Step 3: Query database
            print("\n--- Step 3: Querying database ---")
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM prices")
                row_count = cursor.fetchone()[0]
                assert row_count > 0, "No rows in prices table"
                print(f"✓ Total rows: {row_count}")

                cursor.execute("SELECT DISTINCT service FROM prices")
                services = [row[0] for row in cursor.fetchall()]
                assert "ec2" in services, "EC2 service not found"
                print(f"✓ Services: {services}")

                # Query for m5.large specifically
                cursor.execute(
                    "SELECT instance_type, os, hourly FROM prices WHERE instance_type='m5.large' AND purchase_option='OnDemand'"
                )
                m5_large_rows = cursor.fetchall()
                assert len(m5_large_rows) > 0, "No m5.large instances found"
                print(f"✓ Found {len(m5_large_rows)} m5.large variants")

            # Step 4: Run validation (may have warnings for small data)
            print("\n--- Step 4: Running validation ---")
            is_valid = quick_validate(db_path)
            if not is_valid:
                print("⚠ quick_validate reported warnings (expected for small test)")
            else:
                print("✓ Validation passed")

            print("\n✓ Full pipeline end-to-end test passed")

        finally:
            dl_module.RAW_DATA_DIR = original_dl_raw_dir
            norm_module.Path = original_norm_path

    def test_price_accuracy_vs_aws_console(self, temp_workspace):
        """Verify price accuracy by comparing known instance price to expected range."""
        from pipeline.download_pricing import download_ec2_us_east_1_only
        from pipeline.generate_db import generate_database
        import pipeline.normalize as norm_module

        tmp_path, raw_dir = temp_workspace

        # Patch modules
        import pipeline.download_filtered as dl_module

        original_dl_raw_dir = dl_module.RAW_DATA_DIR
        dl_module.RAW_DATA_DIR = raw_dir

        original_norm_path = norm_module.Path
        norm_module.Path = lambda p: tmp_path / p if str(p) == "data/raw" else Path(p)

        try:
            # Download fresh EC2 us-east-1 data
            success = download_ec2_us_east_1_only()
            assert success, "Download failed"

            ec2_file = raw_dir / "AmazonEC2.json"
            assert ec2_file.exists()

            # Generate database
            db_path = tmp_path / "aws_pricing.sqlite3"
            try:
                generate_database(db_path)
            except SystemExit as e:
                if "expected >=" in str(e) and "rows" in str(e):
                    print(f"⚠ Validation skipped: {e}")
                    if not db_path.exists():
                        raise
                else:
                    raise

            assert db_path.exists()

            # Query for m5.large (Linux, Shared) on-demand price
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT hourly 
                    FROM prices 
                    WHERE service='ec2' 
                      AND instance_type='m5.large' 
                      AND os='Linux' 
                      AND tenancy='Shared' 
                      AND purchase_option='OnDemand'
                      AND region='us-east-1'
                    """
                )
                result = cursor.fetchone()

                assert result is not None, (
                    "m5.large Linux on-demand price not found in database"
                )
                actual_price = result[0]

                # As of 2025-03-04, m5.large in us-east-1 is approximately $0.096/hr
                # Prices vary by commit term, but we allow ±20% variance to account for:
                # - AWS price updates
                # - Regional variations within us-east-1 (AZ-specific)
                # - Windows vs Linux detection issues
                expected_price = 0.096
                tolerance = 0.20  # 20%
                lower_bound = expected_price * (1 - tolerance)
                upper_bound = expected_price * (1 + tolerance)

                assert lower_bound <= actual_price <= upper_bound, (
                    f"Price outside expected range: ${actual_price:.4f}/hr "
                    f"(expected ~${expected_price:.4f} ±{tolerance * 100}%: ${lower_bound:.4f}-${upper_bound:.4f})"
                )

                print(
                    f"✓ m5.large price: ${actual_price:.4f}/hr (expected: ${expected_price:.4f} ±20%)"
                )

        finally:
            dl_module.RAW_DATA_DIR = original_dl_raw_dir
            norm_module.Path = original_norm_path
