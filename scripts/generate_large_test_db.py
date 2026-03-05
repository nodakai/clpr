#!/usr/bin/env python3
"""
Generate a large test database for benchmarking.
Can produce up to ~300MB with realistic data distribution.
"""

import sqlite3
import sys
import random
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path to import pipeline modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.schema import initialize_database, PriceRow
from pipeline.normalize import normalize_product

# =========== CONFIGURATION ===========
TARGET_SIZE_MB = 300  # Target database size (adjust as needed)
TARGET_ROWS_ESTIMATE = 1300000  # Rough estimate for 300MB

# Use a smaller instance set to keep things manageable but realistic
INSTANCE_TYPES = {
    # ~60 realistic instance types across families
    # m5 series (9 types)
    "m5.large": {"vcpu": 2, "memory_gb": 8, "family": "m5", "price": 0.096},
    "m5.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "m5", "price": 0.192},
    "m5.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "m5", "price": 0.384},
    "m5.4xlarge": {"vcpu": 16, "memory_gb": 64, "family": "m5", "price": 0.768},
    "m5.8xlarge": {"vcpu": 32, "memory_gb": 128, "family": "m5", "price": 1.536},
    "m5.12xlarge": {"vcpu": 48, "memory_gb": 192, "family": "m5", "price": 2.304},
    "m5.16xlarge": {"vcpu": 64, "memory_gb": 256, "family": "m5", "price": 3.072},
    "m5.24xlarge": {"vcpu": 96, "memory_gb": 384, "family": "m5", "price": 4.608},
    "m5.metal": {"vcpu": 96, "memory_gb": 384, "family": "m5", "price": 4.608},
    # m6i series (9 types)
    "m6i.large": {"vcpu": 2, "memory_gb": 8, "family": "m6i", "price": 0.096},
    "m6i.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "m6i", "price": 0.192},
    "m6i.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "m6i", "price": 0.384},
    "m6i.4xlarge": {"vcpu": 16, "memory_gb": 64, "family": "m6i", "price": 0.768},
    "m6i.8xlarge": {"vcpu": 32, "memory_gb": 128, "family": "m6i", "price": 1.536},
    "m6i.12xlarge": {"vcpu": 48, "memory_gb": 192, "family": "m6i", "price": 2.304},
    "m6i.16xlarge": {"vcpu": 64, "memory_gb": 256, "family": "m6i", "price": 3.072},
    "m6i.24xlarge": {"vcpu": 96, "memory_gb": 384, "family": "m6i", "price": 4.608},
    "m6i.metal": {"vcpu": 96, "memory_gb": 384, "family": "m6i", "price": 4.608},
    # c5 series (8 types)
    "c5.large": {"vcpu": 2, "memory_gb": 4, "family": "c5", "price": 0.085},
    "c5.xlarge": {"vcpu": 4, "memory_gb": 8, "family": "c5", "price": 0.17},
    "c5.2xlarge": {"vcpu": 8, "memory_gb": 16, "family": "c5", "price": 0.34},
    "c5.4xlarge": {"vcpu": 16, "memory_gb": 32, "family": "c5", "price": 0.68},
    "c5.9xlarge": {"vcpu": 36, "memory_gb": 72, "family": "c5", "price": 1.53},
    "c5.12xlarge": {"vcpu": 48, "memory_gb": 96, "family": "c5", "price": 2.04},
    "c5.18xlarge": {"vcpu": 72, "memory_gb": 144, "family": "c5", "price": 3.06},
    "c5.24xlarge": {"vcpu": 96, "memory_gb": 192, "family": "c5", "price": 4.08},
    # c6i series (8 types)
    "c6i.large": {"vcpu": 2, "memory_gb": 4, "family": "c6i", "price": 0.085},
    "c6i.xlarge": {"vcpu": 4, "memory_gb": 8, "family": "c6i", "price": 0.17},
    "c6i.2xlarge": {"vcpu": 8, "memory_gb": 16, "family": "c6i", "price": 0.34},
    "c6i.4xlarge": {"vcpu": 16, "memory_gb": 32, "family": "c6i", "price": 0.68},
    "c6i.8xlarge": {"vcpu": 32, "memory_gb": 64, "family": "c6i", "price": 1.36},
    "c6i.12xlarge": {"vcpu": 48, "memory_gb": 96, "family": "c6i", "price": 2.04},
    "c6i.16xlarge": {"vcpu": 64, "memory_gb": 128, "family": "c6i", "price": 2.72},
    "c6i.24xlarge": {"vcpu": 96, "memory_gb": 192, "family": "c6i", "price": 4.08},
    # r5 series (9 types)
    "r5.large": {"vcpu": 2, "memory_gb": 16, "family": "r5", "price": 0.126},
    "r5.xlarge": {"vcpu": 4, "memory_gb": 32, "family": "r5", "price": 0.252},
    "r5.2xlarge": {"vcpu": 8, "memory_gb": 64, "family": "r5", "price": 0.504},
    "r5.4xlarge": {"vcpu": 16, "memory_gb": 128, "family": "r5", "price": 1.008},
    "r5.8xlarge": {"vcpu": 32, "memory_gb": 256, "family": "r5", "price": 2.016},
    "r5.12xlarge": {"vcpu": 48, "memory_gb": 384, "family": "r5", "price": 3.024},
    "r5.16xlarge": {"vcpu": 64, "memory_gb": 512, "family": "r5", "price": 4.032},
    "r5.24xlarge": {"vcpu": 96, "memory_gb": 768, "family": "r5", "price": 6.048},
    "r5.metal": {"vcpu": 96, "memory_gb": 768, "family": "r5", "price": 6.048},
    # r6i series (9 types)
    "r6i.large": {"vcpu": 2, "memory_gb": 16, "family": "r6i", "price": 0.126},
    "r6i.xlarge": {"vcpu": 4, "memory_gb": 32, "family": "r6i", "price": 0.252},
    "r6i.2xlarge": {"vcpu": 8, "memory_gb": 64, "family": "r6i", "price": 0.504},
    "r6i.4xlarge": {"vcpu": 16, "memory_gb": 128, "family": "r6i", "price": 1.008},
    "r6i.8xlarge": {"vcpu": 32, "memory_gb": 256, "family": "r6i", "price": 2.016},
    "r6i.12xlarge": {"vcpu": 48, "memory_gb": 384, "family": "r6i", "price": 3.024},
    "r6i.16xlarge": {"vcpu": 64, "memory_gb": 512, "family": "r6i", "price": 4.032},
    "r6i.24xlarge": {"vcpu": 96, "memory_gb": 768, "family": "r6i", "price": 6.048},
    "r6i.metal": {"vcpu": 96, "memory_gb": 768, "family": "r6i", "price": 6.048},
    # t3 series (6 types)
    "t3.micro": {"vcpu": 2, "memory_gb": 1, "family": "t3", "price": 0.0104},
    "t3.small": {"vcpu": 2, "memory_gb": 2, "family": "t3", "price": 0.0208},
    "t3.medium": {"vcpu": 2, "memory_gb": 4, "family": "t3", "price": 0.0416},
    "t3.large": {"vcpu": 2, "memory_gb": 8, "family": "t3", "price": 0.0832},
    "t3.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "t3", "price": 0.1664},
    "t3.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "t3", "price": 0.3328},
    # t4g series (6 types)
    "t4g.micro": {"vcpu": 2, "memory_gb": 1, "family": "t4g", "price": 0.0084},
    "t4g.small": {"vcpu": 2, "memory_gb": 2, "family": "t4g", "price": 0.0168},
    "t4g.medium": {"vcpu": 2, "memory_gb": 4, "family": "t4g", "price": 0.0336},
    "t4g.large": {"vcpu": 2, "memory_gb": 8, "family": "t4g", "price": 0.0672},
    "t4g.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "t4g", "price": 0.1344},
    "t4g.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "t4g", "price": 0.2688},
}

# All major regions (25 regions)
REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "af-south-1",
    "ap-east-1",
    "ap-south-1",
    "ap-northeast-3",
    "ap-northeast-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ca-central-1",
    "cn-north-1",
    "cn-northwest-1",
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-south-1",
    "eu-north-1",
    "me-south-1",
    "sa-east-1",
    "us-gov-east-1",
    "us-gov-west-1",
]

# OS options (4)
OS_LIST = ["Linux", "Windows", "RHEL", "SUSE"]

# Tenancy options (3)
TENANCY_OPTIONS = ["Shared", "Dedicated", "Host"]

# Purchase options (2) + variations
PURCHASE_OPTIONS = ["OnDemand", "Reserved"]
LEASE_TERMS = ["1yr", "3yr"]
PURCHASE_OPTION_RESERVED = ["AllUpfront", "PartialUpfront", "NoUpfront"]
OFFERING_CLASSES = ["standard", "convertible"]

# Storage and network
STORAGE_TYPES = ["EBS", "NVME", "SSD"]
NETWORK_PERFORMANCE = ["Up to 10 Gbps", "Up to 25 Gbps", "50 Gbps", "100 Gbps"]


def region_display_name(region_code: str) -> str:
    """Convert region code to AWS display name."""
    region_map = {
        "us-east-1": "US East (N. Virginia)",
        "us-east-2": "US East (Ohio)",
        "us-west-1": "US West (N. California)",
        "us-west-2": "US West (Oregon)",
        "af-south-1": "Africa (Cape Town)",
        "ap-east-1": "Asia Pacific (Hong Kong)",
        "ap-south-1": "Asia Pacific (Mumbai)",
        "ap-northeast-3": "Asia Pacific (Osaka)",
        "ap-northeast-2": "Asia Pacific (Seoul)",
        "ap-southeast-1": "Asia Pacific (Singapore)",
        "ap-southeast-2": "Asia Pacific (Sydney)",
        "ap-northeast-1": "Asia Pacific (Tokyo)",
        "ca-central-1": "Canada (Central)",
        "cn-north-1": "China (Beijing)",
        "cn-northwest-1": "China (Ningxia)",
        "eu-central-1": "Europe (Frankfurt)",
        "eu-west-1": "Europe (Ireland)",
        "eu-west-2": "Europe (London)",
        "eu-west-3": "Europe (Paris)",
        "eu-south-1": "Europe (Milan)",
        "eu-north-1": "Europe (Stockholm)",
        "me-south-1": "Middle East (Bahrain)",
        "sa-east-1": "South America (São Paulo)",
        "us-gov-east-1": "AWS GovCloud (US-East)",
        "us-gov-west-1": "AWS GovCloud (US-West)",
    }
    return region_map.get(region_code, region_code)


def generate_terms(
    purchase_option: str,
    lease_term: str,
    purchase_option_reserved: str,
    offering_class: str,
    hourly: float,
    upfront_cost: float,
) -> Dict:
    """Generate terms structure similar to AWS API response."""
    if purchase_option == "OnDemand":
        return {
            "OnDemand": {
                "GEN001": {
                    "priceDimensions": {
                        "GEN001": {
                            "rateCode": "GEN001-OnDemand",
                            "pricePerUnit": {"USD": str(hourly)},
                            "unit": "Hrs",
                            "description": "On-Demand",
                        }
                    }
                }
            }
        }
    else:
        reserved_terms = {}
        term_key = f"{lease_term}-{offering_class or 'standard'}"
        reserved_terms[term_key] = {
            "priceDimensions": {
                "GEN002": {
                    "rateCode": f"GEN002-{purchase_option_reserved or 'NoUpfront'}",
                    "pricePerUnit": {"USD": str(hourly)},
                    "unit": "Hrs",
                    "description": f"Reserved {lease_term} {offering_class or ''}",
                }
            }
        }
        if upfront_cost:
            reserved_terms[term_key]["priceDimensions"]["GEN003"] = {
                "rateCode": f"GEN003-{purchase_option_reserved}",
                "pricePerUnit": {"USD": str(upfront_cost / (24 * 365))},
                "unit": "Hrs",
                "description": f"Upfront cost",
            }
        return {"Reserved": reserved_terms}


def generate_large_database(output_path: str, target_rows: int):
    """Generate a large synthetic database."""
    print(f"Generating large test database: {output_path}")
    print(f"Target: ~{target_rows:,} rows (~{TARGET_SIZE_MB}MB)")

    # Calculate expected total combinations
    instance_count = len(INSTANCE_TYPES)
    region_count = len(REGIONS)
    os_count = len(OS_LIST)
    tenancy_count = len(TENANCY_OPTIONS)
    purchase_count = len(PURCHASE_OPTIONS)

    base_combinations = instance_count * region_count * os_count * tenancy_count
    print(
        f"Base combinations: {instance_count} × {region_count} × {os_count} × {tenancy_count} = {base_combinations:,}"
    )

    # To reach target rows, we need variations for Reserved options
    reserved_variations = (
        len(LEASE_TERMS) * len(PURCHASE_OPTION_RESERVED) * len(OFFERING_CLASSES)
    )
    total_combinations = base_combinations * (
        1 + reserved_variations / 2
    )  # Rough estimate
    print(f"Total combinations with Reserved: ~{int(total_combinations):,}")

    multiplier = max(1, int(target_rows // total_combinations))
    print(f"Using multiplier: {multiplier}x (adds random variation)")

    # Create database
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    conn = sqlite3.connect(output_path)
    initialize_database(conn)

    total_inserted = 0
    start_time = datetime.now()

    try:
        # We'll batch insert for performance
        batch_size = 10000
        batch = []

        for instance_type, specs in INSTANCE_TYPES.items():
            base_price = specs["price"]
            family = specs["family"]

            for region in REGIONS:
                region_multiplier = random.uniform(0.7, 1.3)

                for os_type in OS_LIST:
                    os_multiplier = (
                        1.0
                        if os_type == "Linux"
                        else 1.1
                        if os_type == "Windows"
                        else 1.15
                    )

                    for tenancy in TENANCY_OPTIONS:
                        tenancy_multiplier = (
                            1.0
                            if tenancy == "Shared"
                            else 1.5
                            if tenancy == "Dedicated"
                            else 2.0
                        )

                        # On-Demand variations (multiplier times)
                        for variation in range(multiplier):
                            random_variation = random.uniform(0.95, 1.05)
                            hourly = round(
                                base_price
                                * region_multiplier
                                * os_multiplier
                                * tenancy_multiplier
                                * random_variation,
                                4,
                            )
                            monthly = round(hourly * 24 * 30, 4)

                            product = {
                                "product": {
                                    "productFamily": "AmazonEC2",
                                    "attributes": {
                                        "location": region_display_name(region),
                                        "operatingSystem": os_type,
                                        "tenancy": tenancy,
                                        "instanceType": instance_type,
                                        "instanceFamily": family,
                                        "vcpu": str(specs["vcpu"]),
                                        "memory": f"{specs['memory_gb']} GiB",
                                        "storage": "EBS only",
                                        "storageMedia": "EBS",
                                        "networkPerformance": "Up to 10 Gbps",
                                        "physicalProcessor": "Intel Xeon"
                                        if "i" in family
                                        else "AMD EPYC",
                                        "processorFeatures": "Intel AVX, Intel AVX2"
                                        if "i" in family
                                        else "AMD AVX",
                                    },
                                },
                                "terms": generate_terms(
                                    "OnDemand", None, None, None, hourly, None
                                ),
                                "sku": f"TEST-{total_inserted:08d}",
                            }

                            rows = normalize_product(product)
                            if rows:
                                batch.append(rows[0])
                                total_inserted += 1

                                if len(batch) >= batch_size:
                                    _insert_batch(conn, batch)
                                    batch = []
                                    if total_inserted % 100000 == 0:
                                        elapsed = (
                                            datetime.now() - start_time
                                        ).total_seconds()
                                        rate = total_inserted / elapsed
                                        print(
                                            f"  Inserted {total_inserted:,} rows ({rate:.0f} rows/sec)"
                                        )

                        # Reserved variations
                        for variation in range(multiplier):
                            lease_term = random.choice(LEASE_TERMS)
                            purchase_option_reserved = random.choice(
                                PURCHASE_OPTION_RESERVED
                            )
                            offering_class = random.choice(OFFERING_CLASSES)

                            lease_discount = 0.6 if lease_term == "1yr" else 0.55
                            random_variation = random.uniform(0.95, 1.05)

                            hourly = round(
                                base_price
                                * region_multiplier
                                * os_multiplier
                                * tenancy_multiplier
                                * lease_discount
                                * random_variation,
                                4,
                            )

                            if purchase_option_reserved == "AllUpfront":
                                upfront_cost = round(hourly * 24 * 365 * 0.85, 2)
                            elif purchase_option_reserved == "PartialUpfront":
                                upfront_cost = round(hourly * 24 * 365 * 0.5, 2)
                            else:
                                upfront_cost = None

                            monthly = round(hourly * 24 * 30, 4)

                            product = {
                                "product": {
                                    "productFamily": "AmazonEC2",
                                    "attributes": {
                                        "location": region_display_name(region),
                                        "operatingSystem": os_type,
                                        "tenancy": tenancy,
                                        "instanceType": instance_type,
                                        "instanceFamily": family,
                                        "vcpu": str(specs["vcpu"]),
                                        "memory": f"{specs['memory_gb']} GiB",
                                        "storage": "EBS only",
                                        "storageMedia": "EBS",
                                        "networkPerformance": "Up to 10 Gbps",
                                        "physicalProcessor": "Intel Xeon"
                                        if "i" in family
                                        else "AMD EPYC",
                                        "processorFeatures": "Intel AVX, Intel AVX2"
                                        if "i" in family
                                        else "AMD AVX",
                                    },
                                },
                                "terms": generate_terms(
                                    "Reserved",
                                    lease_term,
                                    purchase_option_reserved,
                                    offering_class,
                                    hourly,
                                    upfront_cost,
                                ),
                                "sku": f"TEST-{total_inserted:08d}",
                            }

                            rows = normalize_product(product)
                            if rows:
                                batch.append(rows[0])
                                total_inserted += 1

                                if len(batch) >= batch_size:
                                    _insert_batch(conn, batch)
                                    batch = []
                                    if total_inserted % 100000 == 0:
                                        elapsed = (
                                            datetime.now() - start_time
                                        ).total_seconds()
                                        rate = total_inserted / elapsed
                                        print(
                                            f"  Inserted {total_inserted:,} rows ({rate:.0f} rows/sec)"
                                        )

                        # Check if we've reached target
                        if total_inserted >= target_rows:
                            print(f"Target reached: {total_inserted:,} rows")
                            break
                    if total_inserted >= target_rows:
                        break
                if total_inserted >= target_rows:
                    break
            if total_inserted >= target_rows:
                break

        # Insert any remaining batch
        if batch:
            _insert_batch(conn, batch)

        # Run VACUUM and ANALYZE
        print("\nRunning VACUUM and ANALYZE...")
        conn.execute("VACUUM;")
        conn.execute("ANALYZE;")
        conn.commit()

    finally:
        conn.close()

    # Report
    elapsed_total = (datetime.now() - start_time).total_seconds()
    db_size = os.path.getsize(output_path) / (1024 * 1024)

    print(f"\n✓ Database generated: {output_path}")
    print(f"  Total rows: {total_inserted:,}")
    print(f"  File size: {db_size:.1f} MB")
    print(f"  Total time: {elapsed_total:.1f}s")
    print(f"  Insert rate: {total_inserted / elapsed_total:.0f} rows/sec")

    return {
        "rows": total_inserted,
        "size_mb": db_size,
        "elapsed_seconds": elapsed_total,
    }


def _insert_batch(conn, batch):
    """Insert a batch of PriceRow objects."""
    cursor = conn.cursor()
    for row in batch:
        cursor.execute(
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
    conn.commit()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate large test database for benchmarking"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/benchmark_ec2.sqlite3",
        help="Output database path",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=TARGET_ROWS_ESTIMATE,
        help=f"Target number of rows (default: {TARGET_ROWS_ESTIMATE:,})",
    )
    parser.add_argument(
        "--target-mb",
        type=float,
        default=TARGET_SIZE_MB,
        help=f"Target database size in MB (default: {TARGET_SIZE_MB})",
    )

    args = parser.parse_args()

    # Adjust row target based on size target
    if args.target_mb:
        # Rough estimate: ~230 bytes per row
        estimated_rows = int(args.target_mb * 1024 * 1024 / 230)
        target_rows = min(args.rows, estimated_rows)
    else:
        target_rows = args.rows

    generate_large_database(args.output, target_rows)

    # Copy to frontend if needed
    frontend_dir = Path("frontend/public/data")
    if frontend_dir.exists():
        import shutil

        dest = frontend_dir / Path(args.output).name
        shutil.copy2(args.output, dest)
        print(f"Copied to {dest}")
        print("Run frontend with: VITE_USE_TEST_DB=true npm run dev")


if __name__ == "__main__":
    main()
