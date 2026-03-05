#!/usr/bin/env python3
"""
Create a small test database for development.
Generates ~1000 rows of synthetic AWS pricing data.
"""

import sqlite3
import os
import random
from datetime import datetime

# Database path
DB_DIR = "data"
TEST_DB = os.path.join(DB_DIR, "test_aws_pricing.sqlite3")

# Realistic pricing data (USD/hr) - approximate On-Demand prices
PRICING = {
    "m5.large": 0.096,
    "m5.xlarge": 0.192,
    "m5.2xlarge": 0.384,
    "t3.micro": 0.0104,
    "t3.small": 0.0208,
    "t3.medium": 0.0416,
    "t3.large": 0.0832,
    "c5.large": 0.085,
    "c5.xlarge": 0.17,
    "c5.2xlarge": 0.34,
    "r5.large": 0.126,
    "r5.xlarge": 0.252,
    "r5.2xlarge": 0.504,
    "g4dn.xlarge": 0.526,
    "g4dn.2xlarge": 1.052,
}

# Instance specifications
INSTANCES = {
    "m5.large": {"vcpu": 2, "memory_gb": 8, "network": "Up to 10 Gbps"},
    "m5.xlarge": {"vcpu": 4, "memory_gb": 16, "network": "Up to 10 Gbps"},
    "m5.2xlarge": {"vcpu": 8, "memory_gb": 32, "network": "Up to 10 Gbps"},
    "t3.micro": {"vcpu": 2, "memory_gb": 1, "network": "Up to 5 Gbps"},
    "t3.small": {"vcpu": 2, "memory_gb": 2, "network": "Up to 5 Gbps"},
    "t3.medium": {"vcpu": 2, "memory_gb": 4, "network": "Up to 5 Gbps"},
    "t3.large": {"vcpu": 2, "memory_gb": 8, "network": "Up to 5 Gbps"},
    "c5.large": {"vcpu": 2, "memory_gb": 4, "network": "Up to 10 Gbps"},
    "c5.xlarge": {"vcpu": 4, "memory_gb": 8, "network": "Up to 10 Gbps"},
    "c5.2xlarge": {"vcpu": 8, "memory_gb": 16, "network": "Up to 10 Gbps"},
    "r5.large": {"vcpu": 2, "memory_gb": 16, "network": "Up to 10 Gbps"},
    "r5.xlarge": {"vcpu": 4, "memory_gb": 32, "network": "Up to 10 Gbps"},
    "r5.2xlarge": {"vcpu": 8, "memory_gb": 64, "network": "Up to 10 Gbps"},
    "g4dn.xlarge": {"vcpu": 4, "memory_gb": 16, "network": "25 Gbps"},
    "g4dn.2xlarge": {"vcpu": 8, "memory_gb": 32, "network": "25 Gbps"},
}

REGIONS = [
    "us-east-1",
    "us-west-2",
    "eu-west-1",
    "ap-southeast-1",
    "sa-east-1",
]

OS_LIST = ["Linux", "Windows"]
TENANCY = "Shared"
STORAGE = "EBS only"
SERVICE = "ec2"


def create_schema(conn):
    """Create the prices table schema."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            service TEXT,
            region TEXT,
            instance_type TEXT,
            os TEXT,
            tenancy TEXT,
            vcpu INTEGER,
            memory_gb REAL,
            storage TEXT,
            network_performance TEXT,
            purchase_option TEXT,
            lease_term TEXT,
            upfront_cost REAL,
            hourly REAL,
            monthly REAL,
            last_updated TEXT
        )
    """)

    # Create indexes for better query performance
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_filter ON prices(service, region, os, tenancy, vcpu, hourly)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_instance ON prices(service, instance_type)"
    )
    conn.commit()


def generate_test_data(conn):
    """Generate synthetic test data."""
    rows = []
    last_updated = datetime.now().isoformat()

    for instance_type, specs in INSTANCES.items():
        base_price = PRICING[instance_type]

        for region in REGIONS:
            # Small regional price variation (±10%)
            region_multiplier = random.uniform(0.9, 1.1)

            for os in OS_LIST:
                # Windows has ~10% surcharge
                os_multiplier = 1.1 if os == "Windows" else 1.0

                hourly = round(base_price * region_multiplier * os_multiplier, 4)
                monthly = round(hourly * 24 * 30, 4)

                # On-Demand
                rows.append(
                    (
                        SERVICE,
                        region,
                        instance_type,
                        os,
                        TENANCY,
                        specs["vcpu"],
                        specs["memory_gb"],
                        STORAGE,
                        specs["network"],
                        "OnDemand",
                        None,
                        None,
                        hourly,
                        monthly,
                        last_updated,
                    )
                )

                # Add some Reserved instances (1yr, no upfront ~40% discount)
                if random.random() < 0.3:  # 30% chance of having Reserved pricing
                    reserved_hourly = hourly * 0.6  # ~40% discount
                    reserved_monthly = reserved_hourly * 24 * 30
                    rows.append(
                        (
                            SERVICE,
                            region,
                            instance_type,
                            os,
                            TENANCY,
                            specs["vcpu"],
                            specs["memory_gb"],
                            STORAGE,
                            specs["network"],
                            "Reserved",
                            "1yr",
                            None,
                            round(reserved_hourly, 4),
                            round(reserved_monthly, 4),
                            last_updated,
                        )
                    )

    # Insert all rows
    conn.executemany(
        """
        INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        rows,
    )
    conn.commit()
    print(f"Generated {len(rows)} test rows")


def main():
    # Ensure data directory exists
    os.makedirs(DB_DIR, exist_ok=True)

    # Remove existing test DB if it exists
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    conn = sqlite3.connect(TEST_DB)
    create_schema(conn)
    generate_test_data(conn)
    conn.close()

    # Get file size
    size_mb = os.path.getsize(TEST_DB) / (1024 * 1024)
    print(f"Created {TEST_DB} ({size_mb:.2f} MB)")

    # Copy to frontend public folder if available
    frontend_data_dir = "frontend/public/data"
    if os.path.exists(frontend_data_dir):
        import shutil

        frontend_test_db = os.path.join(frontend_data_dir, "test_aws_pricing.sqlite3")
        shutil.copy2(TEST_DB, frontend_test_db)
        print(f"Copied to {frontend_test_db}")
        print("Start frontend dev server with: VITE_USE_TEST_DB=true npm run dev")
    else:
        print(f"Frontend public/data not found. Copy manually to frontend/public/data/")


if __name__ == "__main__":
    main()
