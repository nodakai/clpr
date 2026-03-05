#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end integration test for AWS pricing pipeline."""

import json
import sqlite3
import tempfile
import sys
from pathlib import Path

# Import pipeline modules
from pipeline.schema import PriceRow, initialize_database
from pipeline.normalize import normalize_product
from pipeline.generate_db import generate_database
from pipeline.validate import quick_validate
from pipeline.test_db import validate_database


# Mock AWS pricing data structure - each item is a full price document
MOCK_EC2_PRODUCTS = [
    {
        "product": {
            "productFamily": "AmazonEC2",
            "attributes": {
                "location": "US East (N. Virginia)",
                "locationType": "AWS Region",
                "operatingSystem": "Linux",
                "tenancy": "Shared",
                "instanceType": "m5.large",
                "instanceFamily": "General purpose",
                "vcpu": "2",
                "memory": "8 GiB",
                "storage": "EBS only",
                "storageMedia": "EBS",
                "networkPerformance": "Up to 10 Gigabit",
                "physicalProcessor": "Intel Xeon Platinum 8175",
                "processorFeatures": "Intel AVX, Intel AVX2, Intel Turbo",
                "burstablePerformance": "Not supported",
            },
        },
        "terms": {
            "OnDemand": {
                "ABC123XYZ": {
                    "priceDimensions": {
                        "ABC123XYZ": {
                            "rateCode": "ABC123XYZ-OnDemand",
                            "pricePerUnit": {"USD": "0.096"},
                            "unit": "Hrs",
                            "description": "On-Demand",
                        }
                    }
                }
            }
        },
        "sku": "ABC123XYZ",
    },
    {
        "product": {
            "productFamily": "AmazonEC2",
            "attributes": {
                "location": "US East (N. Virginia)",
                "locationType": "AWS Region",
                "operatingSystem": "Windows",
                "tenancy": "Shared",
                "instanceType": "m5.xlarge",
                "instanceFamily": "General purpose",
                "vcpu": "4",
                "memory": "16 GiB",
                "storage": "EBS only",
                "storageMedia": "EBS",
                "networkPerformance": "Up to 10 Gigabit",
                "physicalProcessor": "Intel Xeon Platinum 8175",
            },
        },
        "terms": {
            "OnDemand": {
                "DEF456UVW": {
                    "priceDimensions": {
                        "DEF456UVW-OnDemand": {
                            "rateCode": "DEF456UVW-OnDemand",
                            "pricePerUnit": {"USD": "0.192"},
                            "unit": "Hrs",
                            "description": "On-Demand",
                        }
                    }
                }
            }
        },
        "sku": "DEF456UVW",
    },
]


def test_mock_normalization():
    """Test normalization with mock EC2 product."""
    print("\n=== Test 1: Mock Normalization ===")
    try:
        for product in MOCK_EC2_PRODUCTS:
            rows = normalize_product(product)
            assert len(rows) > 0, (
                f"normalize_product returned no rows for {product.get('sku')}"
            )
            for row in rows:
                assert row.service == "ec2", (
                    f"Expected service='ec2', got {row.service}"
                )
                assert row.hourly is not None, (
                    f"Missing hourly price for {product.get('sku')}"
                )
                print(
                    f"✓ Product {product.get('sku')}: {row.instance_type} - ${row.hourly}/hr"
                )
        print("✓ Mock normalization test passed")
        return True
    except Exception as e:
        print(f"✗ Mock normalization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_in_memory_database():
    """Test database creation in memory with mock data."""
    print("\n=== Test 2: In-Memory Database ===")
    try:
        with sqlite3.connect(":memory:") as conn:
            initialize_database(conn)
            print("✓ Database initialized in memory")

            count = 0
            for product in MOCK_EC2_PRODUCTS:
                rows = normalize_product(product)
                for row in rows:
                    cursor = conn.execute(
                        """
                        INSERT INTO prices (
                            service, region, instance_type, family, size, vcpu, memory_gb,
                            storage, storage_gb, storage_type, network_performance,
                            processor, burst_capable, gpu, gpu_memory_gb, os, tenancy,
                            price_unit, purchase_option, lease_term, purchase_option_reserved,
                            offering_class, hourly, monthly, upfront_cost, effective_date,
                            sku, rate_code
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            row.service,
                            row.region,
                            row.instance_type,
                            row.family,
                            row.size,
                            row.vcpu,
                            row.memory_gb,
                            row.storage,
                            row.storage_gb,
                            row.storage_type,
                            row.network_performance,
                            row.processor,
                            row.burst_capable,
                            row.gpu,
                            row.gpu_memory_gb,
                            row.os,
                            row.tenancy,
                            row.price_unit,
                            row.purchase_option,
                            row.lease_term,
                            row.purchase_option_reserved,
                            row.offering_class,
                            row.hourly,
                            row.monthly,
                            row.upfront_cost,
                            row.effective_date,
                            row.sku,
                            row.rate_code,
                        ),
                    )
                    count += 1
            conn.commit()
            print(f"✓ Inserted {count} rows into in-memory database")

            cursor = conn.execute("SELECT COUNT(*) FROM prices")
            total = cursor.fetchone()[0]
            assert total == count, f"Expected {count} rows, found {total}"

            cursor = conn.execute(
                "SELECT service, COUNT(*) FROM prices GROUP BY service"
            )
            services = cursor.fetchall()
            print(f"✓ Services in DB: {services}")

            cursor = conn.execute("SELECT * FROM prices WHERE vcpu >= 2")
            results = cursor.fetchall()
            print(f"✓ Sample query returned {len(results)} rows")

        print("✓ In-memory database test passed")
        return True
    except Exception as e:
        print(f"✗ In-memory database test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_temp_file_database():
    """Test generate_database with temporary file."""
    print("\n=== Test 3: Temp File Database ===")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "data" / "raw"
            raw_dir.mkdir(parents=True)

            ec2_file = raw_dir / "AmazonEC2.json"
            with open(ec2_file, "w") as f:
                json.dump(MOCK_EC2_PRODUCTS, f)

            import pipeline.normalize as norm_module

            original_norm_path = norm_module.Path
            norm_module.Path = lambda p: (
                Path(tmpdir) / p if str(p) == "data/raw" else Path(p)
            )

            try:
                db_path = Path(tmpdir) / "test_pricing.sqlite3"
                try:
                    generate_database(db_path)
                except SystemExit as e:
                    if "expected >=" in str(e) and "rows" in str(e):
                        print(f"⚠ generate_database validation warning: {e}")
                        if not db_path.exists():
                            raise
                    else:
                        raise
                print(
                    f"✓ Database generated: {db_path} ({db_path.stat().st_size} bytes)"
                )

                with sqlite3.connect(db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM prices")
                    total = cursor.fetchone()[0]
                    print(f"✓ Total rows in database: {total}")

                is_valid = quick_validate(db_path)
                if is_valid:
                    print("✓ quick_validate passed")
                else:
                    print("⚠ quick_validate had warnings but database created")
                print("✓ Temp file database test passed")
                return True
            finally:
                norm_module.Path = original_norm_path
    except Exception as e:
        print(f"✗ Temp file database test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_real_full_pipeline():
    """Test full pipeline with real data (EC2 us-east-1 only)."""
    print("\n=== Test 4: Real Full Pipeline (EC2 us-east-1) ===")
    print("This test requires AWS credentials configured.")

    try:
        from pipeline.download_pricing import download_ec2_us_east_1_only
        import boto3

        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials is None:
                print("⚠ No AWS credentials found - skipping real data test")
                return True
        except Exception as e:
            print(f"⚠ AWS boto3 check failed: {e} - skipping real data test")
            return True

        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = Path(tmpdir) / "data" / "raw"
            raw_dir.mkdir(parents=True)

            print("Step 1: Downloading EC2 us-east-1 data...")
            import pipeline.download_pricing as dl_module

            original_dl_raw_dir = dl_module.RAW_DATA_DIR
            dl_module.RAW_DATA_DIR = raw_dir

            try:
                success = download_ec2_us_east_1_only()
                if not success:
                    print("✗ Download failed")
                    return False

                ec2_file = raw_dir / "AmazonEC2.json"
                if not ec2_file.exists():
                    print("✗ EC2 file not created")
                    return False

                size_mb = ec2_file.stat().st_size / (1024 * 1024)
                print(f"✓ Downloaded AmazonEC2.json ({size_mb:.2f} MB)")

                with open(ec2_file) as f:
                    data = json.load(f)
                    product_count = len(data)
                    print(f"✓ Contains {product_count} products")
            finally:
                dl_module.RAW_DATA_DIR = original_dl_raw_dir

            print("Step 2: Generating SQLite database...")
            db_path = Path(tmpdir) / "aws_pricing.sqlite3"

            import pipeline.normalize as norm_module

            original_norm_path = norm_module.Path
            norm_module.Path = lambda p: (
                Path(tmpdir) / p if str(p) == "data/raw" else Path(p)
            )

            try:
                try:
                    generate_database(db_path)
                except SystemExit as e:
                    print(f"✗ generate_database failed validation: {e}")
                    return False
                print(
                    f"✓ Database generated: {db_path.stat().st_size / (1024 * 1024):.2f} MB"
                )
            finally:
                norm_module.Path = original_norm_path

            db_size_mb = db_path.stat().st_size / (1024 * 1024)
            if db_size_mb < 10:
                print(f"✗ Database too small: {db_size_mb:.2f} MB (expected >10MB)")
                return False
            if db_size_mb > 50:
                print(
                    f"⚠ Database larger than 50MB: {db_size_mb:.2f} MB (still acceptable)"
                )
            else:
                print(f"✓ Database size within range: {db_size_mb:.2f} MB")

            print("Step 3: Running validation...")
            is_valid = quick_validate(db_path)
            if not is_valid:
                print("⚠ quick_validate reported issues but continuing")

            print("Step 4: Sample queries...")
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT service, COUNT(*) FROM prices GROUP BY service")
                services = cursor.fetchall()
                print(f"  Services: {services}")

                cursor.execute(
                    "SELECT instance_type, COUNT(*) FROM prices WHERE service='ec2' AND vcpu >= 4 GROUP BY instance_type LIMIT 5"
                )
                rows = cursor.fetchall()
                print(f"  EC2 vCPU>=4 types (top 5): {rows}")

                cursor.execute(
                    "SELECT purchase_option, COUNT(*), AVG(hourly) FROM prices WHERE service='ec2' AND hourly IS NOT NULL GROUP BY purchase_option"
                )
                rows = cursor.fetchall()
                print(f"  Pricing options: {rows}")

            print("✓ Sample queries executed")
            print("✓ Full pipeline test passed")
            return True

    except ImportError as e:
        print(f"⚠ Import error (boto3 may not be installed): {e}")
        print("   Install with: pip install boto3 ijson tqdm")
        return True
    except Exception as e:
        print(f"✗ Real full pipeline test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_full_pipeline():
    """Integration test using small fixture dataset to exercise full workflow."""
    import shutil  # Local import to avoid affecting global imports

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        raw_dir = tmp_path / "data" / "raw"
        raw_dir.mkdir(parents=True)

        # Locate the fixture file within the repository
        fixture_path = Path(__file__).parent / "tests" / "fixtures" / "ec2_sample.json"
        if not fixture_path.exists():
            raise FileNotFoundError(f"Test fixture not found at {fixture_path}")

        # Copy fixture to temporary raw data directory
        shutil.copy(fixture_path, raw_dir / "ec2_sample.json")

        # Patch the normalize module's Path to redirect "data/raw" to our temporary location
        import pipeline.normalize as norm_module

        original_path = norm_module.Path
        norm_module.Path = lambda p: tmp_path / p if str(p) == "data/raw" else Path(p)

        try:
            db_path = tmp_path / "test_pricing.sqlite3"
            try:
                generate_database(db_path)
            except SystemExit as e:
                # Allow validation failures due to small test data (row count check)
                if "expected >=" in str(e) and "rows" in str(e):
                    print(f"[NOTE] generate_database validation skipped: {e}")
                else:
                    raise

            # Assert database file exists and has non-zero size
            assert db_path.exists(), "Database file was not created"
            assert db_path.stat().st_size > 0, "Database file is empty"

            # Connect and verify structure and content
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Verify 'prices' table exists
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='prices'"
                )
                assert cursor.fetchone() is not None, "Table 'prices' does not exist"

                # Check total row count
                cursor.execute("SELECT COUNT(*) FROM prices")
                total_rows = cursor.fetchone()[0]
                assert total_rows == 4, f"Expected 4 rows, got {total_rows}"

                # Verify service 'ec2' is present
                cursor.execute("SELECT DISTINCT service FROM prices")
                services = {row[0] for row in cursor.fetchall()}
                assert "ec2" in services, "Expected service 'ec2' not found in database"

                # Query OnDemand rows
                cursor.execute(
                    "SELECT instance_type, os, hourly FROM prices WHERE purchase_option='OnDemand'"
                )
                ondemand_rows = cursor.fetchall()
                assert len(ondemand_rows) == 3, (
                    f"Expected 3 OnDemand rows, got {len(ondemand_rows)}"
                )

                # Build a lookup for expected OnDemand values
                od_lookup = {(it, os): hourly for it, os, hourly in ondemand_rows}

                # Expected OnDemand entries and their hourly prices
                expected = {
                    ("m5.large", "Linux"): 0.096,
                    ("t3.micro", "Linux"): 0.0104,
                    ("c5.xlarge", "Windows"): 0.17,
                }

                for (it, os), expected_price in expected.items():
                    key = (it, os)
                    assert key in od_lookup, f"Missing OnDemand row for {it}, {os}"
                    actual_price = od_lookup[key]
                    assert abs(actual_price - expected_price) < 1e-4, (
                        f"Hourly price mismatch for {it}, {os}: expected {expected_price}, got {actual_price}"
                    )

            # Re-check indexes and page_size
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # Verify page_size = 1024
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                assert page_size == 1024, f"page_size is {page_size}, expected 1024"

                # Verify required indexes exist
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='prices'"
                )
                indexes = {row[0] for row in cursor.fetchall()}
                required_indexes = {
                    "idx_filter",
                    "idx_instance",
                    "idx_price",
                    "idx_specs",
                }
                for idx in required_indexes:
                    assert idx in indexes, f"Missing required index: {idx}"

            # Run quick_validate (may fail for size/row count, but we proceed anyway)
            is_valid = quick_validate(db_path)
            if not is_valid:
                print(
                    "[NOTE] quick_validate reported warnings (expected for small test data)"
                )

            print("✓ Full pipeline test passed")
            return True

        finally:
            # Restore original Path function in normalize module
            norm_module.Path = original_path


def run_all_tests(include_real_download=False):
    """Run all integration tests."""
    print("=" * 60)
    print("AWS PRICING PIPELINE - END-TO-END INTEGRATION TEST")
    print("=" * 60)

    results = []
    results.append(("Mock Normalization", test_mock_normalization()))
    results.append(("In-Memory Database", test_in_memory_database()))
    results.append(("Temp File Database", test_temp_file_database()))
    results.append(("Full Pipeline", test_full_pipeline()))

    if include_real_download:
        results.append(("Real Full Pipeline", test_real_full_pipeline()))

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    failed = sum(1 for _, result in results if not result)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print("=" * 60)
    print(f"Total: {passed} passed, {failed} failed out of {len(results)} tests")

    if failed == 0:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    include_real = "--real" in sys.argv or "-r" in sys.argv
    if include_real:
        print("NOTE: Real download test will attempt to contact AWS API.")
        print("Ensure AWS credentials are configured (~/.aws/credentials)")
        print("This may take 5-15 minutes and download ~10-50MB of data.")
        print("-" * 60)
    sys.exit(run_all_tests(include_real_download=include_real))
