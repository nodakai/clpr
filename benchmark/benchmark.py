#!/usr/bin/env python3
"""
Comprehensive benchmark suite for AWS Pricing Static application.

Measures:
- Pipeline performance (download, normalize, generate) with timing and memory
- Query performance with EXPLAIN plans and execution times
- HTTP VFS efficiency (requests, bytes transferred)
- Frontend load performance (WASM init, DB open, first query)
"""

import argparse
import json
import sqlite3
import sys
import time
import tracemalloc
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import os

# Add project root to path to import pipeline module
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.schema import PriceRow, initialize_database, CREATE_INDEX_SQLS
from pipeline.normalize import normalize_product

# ==================== BENCHMARK CONFIGURATION ====================

BENCHMARK_CONFIG = {
    "target_db_size_mb": 300,  # Target database size for realistic testing
    "min_rows": 1000000,  # Minimum rows for meaningful benchmarks (~300MB)
    "ec2_services": ["AmazonEC2"],
    "test_queries": [
        {
            "name": "Simple vCPU filter",
            "sql": "SELECT * FROM prices WHERE service='ec2' AND vcpu >= 4 AND os='Linux'",
            "description": "Filter by vCPU and OS",
        },
        {
            "name": "Price range + region",
            "sql": "SELECT * FROM prices WHERE region='us-east-1' AND hourly BETWEEN 0.05 AND 0.20",
            "description": "Regional price range query",
        },
        {
            "name": "Instance type pattern",
            "sql": "SELECT * FROM prices WHERE instance_type LIKE 'm5.%'",
            "description": "LIKE pattern matching on instance type",
        },
        {
            "name": "Reserved options",
            "sql": "SELECT * FROM prices WHERE purchase_option='Reserved' AND lease_term='1yr' AND purchase_option_reserved='AllUpfront'",
            "description": "Reserved instance filtering",
        },
        {
            "name": "Multi-filter complex",
            "sql": "SELECT * FROM prices WHERE vcpu >= 8 AND memory_gb >= 16 AND storage_type='nvme' AND hourly < 1.0",
            "description": "Complex multi-condition query",
        },
    ],
}


# ==================== SYNTHETIC DATA GENERATOR ====================


class SyntheticDataGenerator:
    """Generates realistic AWS pricing data for benchmarking."""

    # Realistic instance types with specs and base prices (us-east-1 On-Demand)
    INSTANCE_TYPES = {
        # General purpose (m5, m6i, m7i series)
        "m5.large": {"vcpu": 2, "memory_gb": 8, "family": "m5", "price": 0.096},
        "m5.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "m5", "price": 0.192},
        "m5.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "m5", "price": 0.384},
        "m5.4xlarge": {"vcpu": 16, "memory_gb": 64, "family": "m5", "price": 0.768},
        "m5.8xlarge": {"vcpu": 32, "memory_gb": 128, "family": "m5", "price": 1.536},
        "m5.12xlarge": {"vcpu": 48, "memory_gb": 192, "family": "m5", "price": 2.304},
        "m5.16xlarge": {"vcpu": 64, "memory_gb": 256, "family": "m5", "price": 3.072},
        "m5.24xlarge": {"vcpu": 96, "memory_gb": 384, "family": "m5", "price": 4.608},
        "m5.metal": {"vcpu": 96, "memory_gb": 384, "family": "m5", "price": 4.608},
        "m6i.large": {"vcpu": 2, "memory_gb": 8, "family": "m6i", "price": 0.096},
        "m6i.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "m6i", "price": 0.192},
        "m6i.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "m6i", "price": 0.384},
        "m6i.4xlarge": {"vcpu": 16, "memory_gb": 64, "family": "m6i", "price": 0.768},
        "m6i.8xlarge": {"vcpu": 32, "memory_gb": 128, "family": "m6i", "price": 1.536},
        "m6i.12xlarge": {"vcpu": 48, "memory_gb": 192, "family": "m6i", "price": 2.304},
        "m6i.16xlarge": {"vcpu": 64, "memory_gb": 256, "family": "m6i", "price": 3.072},
        "m6i.24xlarge": {"vcpu": 96, "memory_gb": 384, "family": "m6i", "price": 4.608},
        "m6i.metal": {"vcpu": 96, "memory_gb": 384, "family": "m6i", "price": 4.608},
        "m7i.large": {"vcpu": 2, "memory_gb": 8, "family": "m7i", "price": 0.096},
        "m7i.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "m7i", "price": 0.192},
        "m7i.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "m7i", "price": 0.384},
        "m7i.4xlarge": {"vcpu": 16, "memory_gb": 64, "family": "m7i", "price": 0.768},
        "m7i.8xlarge": {"vcpu": 32, "memory_gb": 128, "family": "m7i", "price": 1.536},
        "m7i.12xlarge": {"vcpu": 48, "memory_gb": 192, "family": "m7i", "price": 2.304},
        "m7i.16xlarge": {"vcpu": 64, "memory_gb": 256, "family": "m7i", "price": 3.072},
        "m7i.24xlarge": {"vcpu": 96, "memory_gb": 384, "family": "m7i", "price": 4.608},
        "m7i.metal": {"vcpu": 96, "memory_gb": 384, "family": "m7i", "price": 4.608},
        # Compute optimized (c5, c6i, c7i series)
        "c5.large": {"vcpu": 2, "memory_gb": 4, "family": "c5", "price": 0.085},
        "c5.xlarge": {"vcpu": 4, "memory_gb": 8, "family": "c5", "price": 0.17},
        "c5.2xlarge": {"vcpu": 8, "memory_gb": 16, "family": "c5", "price": 0.34},
        "c5.4xlarge": {"vcpu": 16, "memory_gb": 32, "family": "c5", "price": 0.68},
        "c5.9xlarge": {"vcpu": 36, "memory_gb": 72, "family": "c5", "price": 1.53},
        "c5.12xlarge": {"vcpu": 48, "memory_gb": 96, "family": "c5", "price": 2.04},
        "c5.18xlarge": {"vcpu": 72, "memory_gb": 144, "family": "c5", "price": 3.06},
        "c5.24xlarge": {"vcpu": 96, "memory_gb": 192, "family": "c5", "price": 4.08},
        "c5.metal": {"vcpu": 96, "memory_gb": 192, "family": "c5", "price": 4.08},
        "c6i.large": {"vcpu": 2, "memory_gb": 4, "family": "c6i", "price": 0.085},
        "c6i.xlarge": {"vcpu": 4, "memory_gb": 8, "family": "c6i", "price": 0.17},
        "c6i.2xlarge": {"vcpu": 8, "memory_gb": 16, "family": "c6i", "price": 0.34},
        "c6i.4xlarge": {"vcpu": 16, "memory_gb": 32, "family": "c6i", "price": 0.68},
        "c6i.8xlarge": {"vcpu": 32, "memory_gb": 64, "family": "c6i", "price": 1.36},
        "c6i.12xlarge": {"vcpu": 48, "memory_gb": 96, "family": "c6i", "price": 2.04},
        "c6i.16xlarge": {"vcpu": 64, "memory_gb": 128, "family": "c6i", "price": 2.72},
        "c6i.24xlarge": {"vcpu": 96, "memory_gb": 192, "family": "c6i", "price": 4.08},
        "c6i.metal": {"vcpu": 96, "memory_gb": 192, "family": "c6i", "price": 4.08},
        "c7i.large": {"vcpu": 2, "memory_gb": 4, "family": "c7i", "price": 0.085},
        "c7i.xlarge": {"vcpu": 4, "memory_gb": 8, "family": "c7i", "price": 0.17},
        "c7i.2xlarge": {"vcpu": 8, "memory_gb": 16, "family": "c7i", "price": 0.34},
        "c7i.4xlarge": {"vcpu": 16, "memory_gb": 32, "family": "c7i", "price": 0.68},
        "c7i.8xlarge": {"vcpu": 32, "memory_gb": 64, "family": "c7i", "price": 1.36},
        "c7i.12xlarge": {"vcpu": 48, "memory_gb": 96, "family": "c7i", "price": 2.04},
        "c7i.16xlarge": {"vcpu": 64, "memory_gb": 128, "family": "c7i", "price": 2.72},
        "c7i.24xlarge": {"vcpu": 96, "memory_gb": 192, "family": "c7i", "price": 4.08},
        "c7i.metal": {"vcpu": 96, "memory_gb": 192, "family": "c7i", "price": 4.08},
        # Memory optimized (r5, r6i, r7i series)
        "r5.large": {"vcpu": 2, "memory_gb": 16, "family": "r5", "price": 0.126},
        "r5.xlarge": {"vcpu": 4, "memory_gb": 32, "family": "r5", "price": 0.252},
        "r5.2xlarge": {"vcpu": 8, "memory_gb": 64, "family": "r5", "price": 0.504},
        "r5.4xlarge": {"vcpu": 16, "memory_gb": 128, "family": "r5", "price": 1.008},
        "r5.8xlarge": {"vcpu": 32, "memory_gb": 256, "family": "r5", "price": 2.016},
        "r5.12xlarge": {"vcpu": 48, "memory_gb": 384, "family": "r5", "price": 3.024},
        "r5.16xlarge": {"vcpu": 64, "memory_gb": 512, "family": "r5", "price": 4.032},
        "r5.24xlarge": {"vcpu": 96, "memory_gb": 768, "family": "r5", "price": 6.048},
        "r5.metal": {"vcpu": 96, "memory_gb": 768, "family": "r5", "price": 6.048},
        "r6i.large": {"vcpu": 2, "memory_gb": 16, "family": "r6i", "price": 0.126},
        "r6i.xlarge": {"vcpu": 4, "memory_gb": 32, "family": "r6i", "price": 0.252},
        "r6i.2xlarge": {"vcpu": 8, "memory_gb": 64, "family": "r6i", "price": 0.504},
        "r6i.4xlarge": {"vcpu": 16, "memory_gb": 128, "family": "r6i", "price": 1.008},
        "r6i.8xlarge": {"vcpu": 32, "memory_gb": 256, "family": "r6i", "price": 2.016},
        "r6i.12xlarge": {"vcpu": 48, "memory_gb": 384, "family": "r6i", "price": 3.024},
        "r6i.16xlarge": {"vcpu": 64, "memory_gb": 512, "family": "r6i", "price": 4.032},
        "r6i.24xlarge": {"vcpu": 96, "memory_gb": 768, "family": "r6i", "price": 6.048},
        "r6i.metal": {"vcpu": 96, "memory_gb": 768, "family": "r6i", "price": 6.048},
        "r7i.large": {"vcpu": 2, "memory_gb": 16, "family": "r7i", "price": 0.126},
        "r7i.xlarge": {"vcpu": 4, "memory_gb": 32, "family": "r7i", "price": 0.252},
        "r7i.2xlarge": {"vcpu": 8, "memory_gb": 64, "family": "r7i", "price": 0.504},
        "r7i.4xlarge": {"vcpu": 16, "memory_gb": 128, "family": "r7i", "price": 1.008},
        "r7i.8xlarge": {"vcpu": 32, "memory_gb": 256, "family": "r7i", "price": 2.016},
        "r7i.12xlarge": {"vcpu": 48, "memory_gb": 384, "family": "r7i", "price": 3.024},
        "r7i.16xlarge": {"vcpu": 64, "memory_gb": 512, "family": "r7i", "price": 4.032},
        "r7i.24xlarge": {"vcpu": 96, "memory_gb": 768, "family": "r7i", "price": 6.048},
        "r7i.metal": {"vcpu": 96, "memory_gb": 768, "family": "r7i", "price": 6.048},
        # Burstable (t3, t4g series)
        "t3.micro": {"vcpu": 2, "memory_gb": 1, "family": "t3", "price": 0.0104},
        "t3.small": {"vcpu": 2, "memory_gb": 2, "family": "t3", "price": 0.0208},
        "t3.medium": {"vcpu": 2, "memory_gb": 4, "family": "t3", "price": 0.0416},
        "t3.large": {"vcpu": 2, "memory_gb": 8, "family": "t3", "price": 0.0832},
        "t3.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "t3", "price": 0.1664},
        "t3.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "t3", "price": 0.3328},
        "t4g.micro": {"vcpu": 2, "memory_gb": 1, "family": "t4g", "price": 0.0084},
        "t4g.small": {"vcpu": 2, "memory_gb": 2, "family": "t4g", "price": 0.0168},
        "t4g.medium": {"vcpu": 2, "memory_gb": 4, "family": "t4g", "price": 0.0336},
        "t4g.large": {"vcpu": 2, "memory_gb": 8, "family": "t4g", "price": 0.0672},
        "t4g.xlarge": {"vcpu": 4, "memory_gb": 16, "family": "t4g", "price": 0.1344},
        "t4g.2xlarge": {"vcpu": 8, "memory_gb": 32, "family": "t4g", "price": 0.2688},
        # High memory (x2, x2iezn, u series)
        "x2gd.large": {"vcpu": 2, "memory_gb": 16, "family": "x2gd", "price": 0.156},
        "x2gd.xlarge": {"vcpu": 4, "memory_gb": 32, "family": "x2gd", "price": 0.312},
        "x2gd.2xlarge": {"vcpu": 8, "memory_gb": 64, "family": "x2gd", "price": 0.624},
        "x2gd.4xlarge": {
            "vcpu": 16,
            "memory_gb": 128,
            "family": "x2gd",
            "price": 1.248,
        },
        "x2gd.8xlarge": {
            "vcpu": 32,
            "memory_gb": 256,
            "family": "x2gd",
            "price": 2.496,
        },
        "x2gd.12xlarge": {
            "vcpu": 48,
            "memory_gb": 384,
            "family": "x2gd",
            "price": 3.744,
        },
        "x2gd.16xlarge": {
            "vcpu": 64,
            "memory_gb": 512,
            "family": "x2gd",
            "price": 4.992,
        },
        "x2iezn.2xlarge": {
            "vcpu": 8,
            "memory_gb": 64,
            "family": "x2iezn",
            "price": 0.624,
        },
        "x2iezn.4xlarge": {
            "vcpu": 16,
            "memory_gb": 128,
            "family": "x2iezn",
            "price": 1.248,
        },
        "x2iezn.8xlarge": {
            "vcpu": 32,
            "memory_gb": 256,
            "family": "x2iezn",
            "price": 2.496,
        },
        "x2iezn.12xlarge": {
            "vcpu": 48,
            "memory_gb": 384,
            "family": "x2iezn",
            "price": 3.744,
        },
        "x2iezn.16xlarge": {
            "vcpu": 64,
            "memory_gb": 512,
            "family": "x2iezn",
            "price": 4.992,
        },
        "x2iezn.metal": {
            "vcpu": 96,
            "memory_gb": 768,
            "family": "x2iezn",
            "price": 7.488,
        },
        "u-6tb1.metal": {"vcpu": 96, "memory_gb": 6144, "family": "u", "price": 36.0},
        "u-9tb1.metal": {"vcpu": 96, "memory_gb": 9216, "family": "u", "price": 54.0},
        "u-12tb1.metal": {"vcpu": 96, "memory_gb": 12288, "family": "u", "price": 72.0},
    }

    # All AWS regions
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

    OS_LIST = ["Linux", "Windows", "RHEL", "SUSE"]
    TENANCY_OPTIONS = ["Shared", "Dedicated", "Host"]
    PURCHASE_OPTIONS = ["OnDemand", "Reserved"]
    LEASE_TERMS = [None, "1yr", "3yr"]
    PURCHASE_OPTION_RESERVED = [None, "AllUpfront", "PartialUpfront", "NoUpfront"]
    OFFERING_CLASSES = [None, "standard", "convertible"]

    # Storage types and network performance
    STORAGE_TYPES = ["EBS", "NVME", "SSD"]
    NETWORK_PERFORMANCE = ["Up to 10 Gbps", "Up to 25 Gbps", "50 Gbps", "100 Gbps"]

    def generate_products(self, num_rows_target: int) -> List[PriceRow]:
        """Generate synthetic pricing data to reach target row count."""
        products = []
        instance_types = list(self.INSTANCE_TYPES.keys())

        # Calculate how many variations per base config we need
        base_configs = len(instance_types) * len(self.REGIONS) * len(self.OS_LIST)
        # Add tenancy variations
        base_configs *= len(self.TENANCY_OPTIONS)
        # Add purchase option variations
        base_configs *= len(self.PURCHASE_OPTIONS)

        print(f"Generating synthetic data...")
        print(f"  Instance types: {len(instance_types)}")
        print(f"  Regions: {len(self.REGIONS)}")
        print(f"  Base configs: {base_configs:,}")

        # If we need more rows than base configs, we'll need to add variations
        # like different lease terms, offering classes, etc.
        multiplier = max(1, num_rows_target // base_configs)
        print(f"  Multiplier needed: {multiplier}x")

        row_count = 0
        for instance_type in instance_types:
            specs = self.INSTANCE_TYPES[instance_type]
            base_price = specs["price"]
            family = specs["family"]

            for region in self.REGIONS:
                # Regional price variation (±30%)
                import random

                region_multiplier = random.uniform(0.7, 1.3)

                for os_type in self.OS_LIST:
                    # OS pricing variation
                    os_multiplier = (
                        1.0
                        if os_type == "Linux"
                        else 1.1
                        if os_type == "Windows"
                        else 1.15
                    )

                    for tenancy in self.TENANCY_OPTIONS:
                        # Tenancy price adjustment
                        tenancy_multiplier = (
                            1.0
                            if tenancy == "Shared"
                            else 1.5
                            if tenancy == "Dedicated"
                            else 2.0
                        )

                        for purchase_option in self.PURCHASE_OPTIONS:
                            # Generate one or multiple variations based on multiplier
                            for variation in range(multiplier):
                                # Add slight random variation (±5%)
                                random_variation = random.uniform(0.95, 1.05)

                                if purchase_option == "OnDemand":
                                    hourly = round(
                                        base_price
                                        * region_multiplier
                                        * os_multiplier
                                        * tenancy_multiplier
                                        * random_variation,
                                        4,
                                    )
                                    lease_term = None
                                    purchase_option_reserved = None
                                    offering_class = None
                                    upfront_cost = None
                                else:  # Reserved
                                    # Reserved gets discount based on lease term and upfront
                                    lease_term = random.choice(
                                        self.LEASE_TERMS[1:]
                                    )  # Skip None
                                    purchase_option_reserved = random.choice(
                                        self.PURCHASE_OPTION_RESERVED[1:]
                                    )
                                    offering_class = random.choice(
                                        self.OFFERING_CLASSES[1:]
                                    )

                                    # Discount factors
                                    lease_discount = (
                                        0.6 if lease_term == "1yr" else 0.55
                                    )  # 3yr gets slightly more

                                    hourly = round(
                                        base_price
                                        * region_multiplier
                                        * os_multiplier
                                        * tenancy_multiplier
                                        * lease_discount
                                        * random_variation,
                                        4,
                                    )

                                    # Upfront cost varies by payment option
                                    if purchase_option_reserved == "AllUpfront":
                                        # Pay full year upfront
                                        upfront_cost = round(
                                            hourly * 24 * 365 * 0.85, 2
                                        )  # 15% discount for AllUpfront
                                    elif purchase_option_reserved == "PartialUpfront":
                                        upfront_cost = round(hourly * 24 * 365 * 0.5, 2)
                                    else:
                                        upfront_cost = None

                                monthly = round(hourly * 24 * 30, 4)

                                # Pick random specs
                                storage_type = random.choice(self.STORAGE_TYPES)
                                network = random.choice(self.NETWORK_PERFORMANCE)
                                storage_gb = (
                                    random.choice([0, 100, 200, 500, 1000, 2000])
                                    if storage_type != "EBS"
                                    else 0
                                )
                                storage = (
                                    f"{storage_gb} GiB"
                                    if storage_gb > 0
                                    else "EBS only"
                                )
                                burst_capable = (
                                    random.choice([True, False])
                                    if family in ["t3", "t4g"]
                                    else None
                                )
                                gpu = 0
                                gpu_memory = None

                                # Create product-like structure
                                product = {
                                    "product": {
                                        "productFamily": "AmazonEC2",
                                        "attributes": {
                                            "location": self._region_display_name(
                                                region
                                            ),
                                            "operatingSystem": os_type,
                                            "tenancy": tenancy,
                                            "instanceType": instance_type,
                                            "instanceFamily": family,
                                            "vcpu": str(specs["vcpu"]),
                                            "memory": f"{specs['memory_gb']} GiB",
                                            "storage": "EBS only",
                                            "storageMedia": storage_type
                                            if storage_type != "EBS"
                                            else "EBS",
                                            "networkPerformance": network,
                                            "physicalProcessor": "Intel Xeon"
                                            if "i" in family
                                            else "AMD EPYC",
                                            "processorFeatures": "Intel AVX, Intel AVX2"
                                            if "i" in family
                                            else "AMD AVX",
                                        },
                                    },
                                    "terms": self._generate_terms(
                                        purchase_option,
                                        lease_term,
                                        purchase_option_reserved,
                                        offering_class,
                                        hourly,
                                        upfront_cost,
                                    ),
                                    "sku": f"TEST-{row_count:08d}",
                                }

                                products.append(product)
                                row_count += 1

                                if row_count >= num_rows_target:
                                    break
                            if row_count >= num_rows_target:
                                break
                        if row_count >= num_rows_target:
                            break
                    if row_count >= num_rows_target:
                        break
                if row_count >= num_rows_target:
                    break
            if row_count >= num_rows_target:
                break

        print(f"Generated {row_count:,} rows")
        return products

    def _region_display_name(self, region_code: str) -> str:
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

    def _generate_terms(
        self,
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
                    "TEST001": {
                        "priceDimensions": {
                            "TEST001": {
                                "rateCode": "TEST001-OnDemand",
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
                    "TEST002": {
                        "rateCode": f"TEST002-{purchase_option_reserved or 'NoUpfront'}",
                        "pricePerUnit": {"USD": str(hourly)},
                        "unit": "Hrs",
                        "description": f"Reserved {lease_term} {offering_class or ''}",
                    }
                }
            }
            if upfront_cost:
                reserved_terms[term_key]["priceDimensions"]["TEST003"] = {
                    "rateCode": f"TEST003-{purchase_option_reserved}",
                    "pricePerUnit": {
                        "USD": str(upfront_cost / (24 * 365))
                    },  # Convert to hourly equivalent
                    "unit": "Hrs",
                    "description": f"Upfront cost",
                }
            return {"Reserved": reserved_terms}


# ==================== BENCHMARK RUNNER ====================


class BenchmarkRunner:
    """Main benchmark orchestration."""

    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "pipeline": {},
            "queries": [],
            "frontend": {},
            "summary": {},
        }

    def time_stage(self, name: str, func, *args, **kwargs):
        """Time a function with memory tracking."""
        print(f"\n{'=' * 60}")
        print(f"Timing: {name}")
        print(f"{'=' * 60}")

        tracemalloc.start()
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"✓ {name} completed in {elapsed:.2f}s")
        print(f"  Peak memory: {peak / 1024 / 1024:.1f} MB")

        return {
            "elapsed_seconds": elapsed,
            "peak_memory_mb": peak / 1024 / 1024,
            "result": result,
        }

    def benchmark_pipeline(self, db_path: str, num_rows_target: int = None):
        """Benchmark the full pipeline (download simulation → normalize → generate)."""
        print("\n" + "=" * 80)
        print("PIPELINE BENCHMARK")
        print("=" * 80)

        # Determine target rows from existing DB or config
        if num_rows_target is None:
            # Check if we can use existing test DB to estimate
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.execute("SELECT COUNT(*) FROM prices")
                    existing_rows = cursor.fetchone()[0]
                    conn.close()
                    if existing_rows >= 1000000:
                        num_rows_target = existing_rows
                        print(f"Using existing DB with {existing_rows:,} rows")
                    else:
                        num_rows_target = BENCHMARK_CONFIG["min_rows"]
                except:
                    num_rows_target = BENCHMARK_CONFIG["min_rows"]
            else:
                num_rows_target = BENCHMARK_CONFIG["min_rows"]

        print(f"Target rows: {num_rows_target:,}")

        # Stage 0: Generate synthetic data (simulating download)
        def generate_data_stage():
            generator = SyntheticDataGenerator()
            products = generator.generate_products(num_rows_target)
            return products

        gen_result = self.time_stage(
            "Data Generation (simulating download)", generate_data_stage
        )
        products = gen_result["result"]

        # Stage 1: Normalize + database population
        def normalize_stage(products):
            # Create in-memory DB for timing normalization
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
                tmp_path = tmp.name

            try:
                conn = sqlite3.connect(tmp_path)
                initialize_database(conn)

                start = time.time()
                total_rows = 0
                for product in products:
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
                        total_rows += 1
                conn.commit()
                conn.execute("VACUUM;")
                conn.execute("ANALYZE;")
                conn.close()
                elapsed = time.time() - start

                # Get DB size
                db_size = os.path.getsize(tmp_path) / (1024 * 1024)

                # Cleanup
                os.unlink(tmp_path)

                return {"rows": total_rows, "size_mb": db_size, "elapsed": elapsed}
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise e

        norm_result = self.time_stage(
            "Normalization + DB Generation", normalize_stage, products
        )

        # Store pipeline results
        self.results["pipeline"] = {
            "target_rows": num_rows_target,
            "generated_rows": len(products),
            "data_generation": {
                "elapsed_seconds": gen_result["elapsed_seconds"],
                "peak_memory_mb": gen_result["peak_memory_mb"],
            },
            "normalization": {
                "elapsed_seconds": norm_result["elapsed_seconds"],
                "peak_memory_mb": norm_result[
                    "peak_memory_mb"
                ],  # This is actually the peak during normalization only
                "rows_inserted": norm_result["result"]["rows"],
                "final_db_size_mb": norm_result["result"]["size_mb"],
            },
        }

        print(f"\nPipeline Summary:")
        print(f"  Total rows: {norm_result['result']['rows']:,}")
        print(f"  DB size: {norm_result['result']['size_mb']:.1f} MB")
        print(f"  Data generation: {gen_result['elapsed_seconds']:.1f}s")
        print(f"  Normalization: {norm_result['elapsed_seconds']:.1f}s")
        print(
            f"  Total: {gen_result['elapsed_seconds'] + norm_result['elapsed_seconds']:.1f}s"
        )

    def benchmark_queries(self, db_path: str):
        """Benchmark query performance with EXPLAIN ANALYZE."""
        print("\n" + "=" * 80)
        print("QUERY PERFORMANCE BENCHMARK")
        print("=" * 80)

        if not os.path.exists(db_path):
            print(f"Database not found: {db_path}")
            print("Skipping query benchmarks.")
            return

        conn = sqlite3.connect(db_path)

        # Get total row count first
        cursor = conn.execute("SELECT COUNT(*) FROM prices")
        total_rows = cursor.fetchone()[0]
        print(f"Database contains {total_rows:,} rows")

        query_results = []

        for query_config in BENCHMARK_CONFIG["test_queries"]:
            name = query_config["name"]
            sql = query_config["sql"]

            print(f"\n{'-' * 60}")
            print(f"Query: {name}")
            print(f"SQL: {sql}")
            print(f"{'-' * 60}")

            # Get EXPLAIN QUERY PLAN
            try:
                cursor = conn.execute(f"EXPLAIN QUERY PLAN {sql}")
                plan_rows = cursor.fetchall()
                plan_text = " | ".join(
                    " ".join(str(col) for col in row) for row in plan_rows
                )
                print(f"Plan: {plan_text}")

                # Analyze plan for index usage
                uses_index = any(
                    idx in plan_text.upper()
                    for idx in [
                        "IDX_FILTER",
                        "IDX_INSTANCE",
                        "IDX_PRICE",
                        "IDX_SPECS",
                        "USING INDEX",
                    ]
                )
                full_scan = (
                    "SCAN TABLE" in plan_text.upper()
                    and "USING INDEX" not in plan_text.upper()
                )
            except Exception as e:
                print(f"Failed to get query plan: {e}")
                plan_text = str(e)
                uses_index = False
                full_scan = False

            # Execute query and time it
            start = time.time()
            try:
                cursor = conn.execute(sql)
                results = cursor.fetchall()
                result_count = len(results)
                elapsed = time.time() - start

                print(f"✓ Returned {result_count:,} rows in {elapsed:.3f}s")
            except Exception as e:
                print(f"✗ Query failed: {e}")
                elapsed = None
                result_count = None

            query_results.append(
                {
                    "name": name,
                    "sql": sql,
                    "plan": plan_text,
                    "uses_index": uses_index,
                    "full_scan_warning": full_scan,
                    "result_count": result_count,
                    "elapsed_seconds": elapsed,
                }
            )

        conn.close()

        self.results["queries"] = query_results

        # Summary
        print(f"\n{'=' * 60}")
        print("Query Benchmark Summary")
        print(f"{'=' * 60}")
        for qr in query_results:
            status = (
                "✓"
                if qr["elapsed_seconds"] and qr["elapsed_seconds"] < 1.0
                else "⚠"
                if qr["elapsed_seconds"]
                else "✗"
            )
            idx = (
                "✓ idx"
                if qr["uses_index"]
                else "✗ no idx"
                if qr["full_scan_warning"]
                else "?"
            )
            print(
                f"{status} {qr['name']:<30} {qr['elapsed_seconds'] if qr['elapsed_seconds'] else 'FAIL':>6.3f}s  {idx}"
            )

    def benchmark_http_vfs(self, db_path: str):
        """Benchmark HTTP VFS efficiency metrics.
        Note: This requires running in a browser environment with fetch tracking.
        For CLI-only benchmarking, we'll provide estimates based on page_size.
        """
        print("\n" + "=" * 80)
        print("HTTP VFS EFFICIENCY ANALYSIS")
        print("=" * 80)

        if not os.path.exists(db_path):
            print(f"Database not found: {db_path}")
            return

        db_size = os.path.getsize(db_path)
        page_size = 1024  # Current setting from schema.py

        # Estimate typical query patterns
        print(f"Database file size: {db_size / (1024 * 1024):.1f} MB")
        print(f"Page size: {page_size} bytes")
        print(f"Total pages: {db_size // page_size:,}")

        # Analyze potential HTTP requests based on query patterns
        estimates = []

        for query_config in BENCHMARK_CONFIG["test_queries"]:
            name = query_config["name"]
            sql = query_config["sql"]

            # Very rough estimation: count filters that might use indexes
            # Index lookups typically need: index pages + data pages
            # Range scans need: index pages + data pages for matching rows

            # For estimation, assume:
            # - Index lookup: reads ~100-500 pages
            # - Full scan: reads ~0.1-1% of DB for filter, plus result rows

            has_vcpu = "vcpu" in sql
            has_hourly = "hourly" in sql
            has_like = "LIKE" in sql
            has_range = "BETWEEN" in sql

            estimated_pages = 0
            if has_like and "%" in sql:
                # LIKE with leading wildcard or wildcard in middle often requires scan
                estimated_pages = int(db_size // page_size * 0.1)  # ~10% of DB
            elif has_vcpu or has_hourly:
                # Range query on indexed column
                estimated_pages = 500  # Typical for indexed range query
            else:
                estimated_pages = 200

            estimated_bytes = estimated_pages * page_size
            estimated_requests = max(
                1, estimated_pages // 10
            )  # With connection pooling, ~10 pages per request

            estimates.append(
                {
                    "query": name,
                    "estimated_pages": estimated_pages,
                    "estimated_bytes_kb": estimated_bytes / 1024,
                    "estimated_requests": estimated_requests,
                    "transfer_overhead_pct": (estimated_bytes / db_size) * 100,
                }
            )

        print(f"\nEstimated HTTP VFS efficiency (based on page_size={page_size}):")
        print(f"{'Query':<30} {'Pages':>10} {'Bytes':>10} {'Req':>6} {'Overhead':>8}")
        print("-" * 80)
        for est in estimates:
            print(
                f"{est['query']:<30} {est['estimated_pages']:>10,} "
                f"{est['estimated_bytes_kb']:>9.0f}KB {est['estimated_requests']:>6} "
                f"{est['transfer_overhead_pct']:>7.1f}%"
            )

        avg_overhead = sum(e["transfer_overhead_pct"] for e in estimates) / len(
            estimates
        )
        print(f"\nAverage transfer overhead: {avg_overhead:.1f}% (target: <10%)")

        self.results["http_vfs"] = {
            "page_size": page_size,
            "db_size_mb": db_size / (1024 * 1024),
            "total_pages": db_size // page_size,
            "estimates": estimates,
            "avg_overhead_pct": avg_overhead,
        }

    def benchmark_frontend_load(self):
        """Frontend load performance requires browser automation.
        For CLI benchmark, we provide estimates and recommendations."""
        print("\n" + "=" * 80)
        print("FRONTEND LOAD TIME ANALYSIS")
        print("=" * 80)

        # Check WASM file size
        wasm_path = (
            Path("frontend/dist/assets") if os.path.exists("frontend/dist") else None
        )
        if wasm_path and wasm_path.exists():
            wasm_files = list(wasm_path.glob("*.wasm"))
            if wasm_files:
                wasm_size = wasm_files[0].stat().st_size
                print(f"WASM file size: {wasm_size / 1024:.0f} KB")
                print(f"  (gzipped estimate: ~{wasm_size * 0.15 / 1024:.0f} KB)")

        print(
            "\nFrontend load time measurement requires browser automation (Puppeteer/Playwright)."
        )
        print("Recommended measurements:")
        print("  1. WASM download + compile time")
        print("  2. Database metadata fetch (initial HTTP requests)")
        print("  3. Time to first query execution")
        print("  4. Time to interactive")

        # Estimate based on network and typical sizes
        wasm_size_kb = 1500  # Typical SQLite WASM ~1.5MB gzipped
        db_metadata_kb = 50  # Fetching initial DB pages for schema
        network_kbps = 10000  # Assume 10 Mbps connection

        wasm_time = wasm_size_kb * 8 / network_kbps  # seconds
        metadata_time = db_metadata_kb * 8 / network_kbps

        print(f"\nEstimated load times on 10 Mbps connection:")
        print(f"  WASM load + init: {wasm_time:.1f}s")
        print(f"  DB metadata fetch: {metadata_time:.1f}s")
        print(f"  Total to first query: {wasm_time + metadata_time:.1f}s")

        self.results["frontend"] = {
            "wasm_size_kb": wasm_size_kb,
            "db_metadata_kb": db_metadata_kb,
            "estimated_load_seconds": wasm_time + metadata_time,
            "note": "Estimates only - run with Puppeteer for actual measurements",
        }

    def save_results(self):
        """Save benchmark results to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"benchmark_{timestamp}.json"

        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)

        print(f"\n✓ Results saved to: {output_file}")

        # Also save a summary as markdown
        summary_file = self.output_dir / f"summary_{timestamp}.md"
        self._write_summary_md(summary_file)
        print(f"✓ Summary saved to: {summary_file}")

    def _write_summary_md(self, filepath: Path):
        """Write a human-readable markdown summary."""
        with open(filepath, "w") as f:
            f.write("# AWS Pricing Static - Benchmark Results\n\n")
            f.write(f"**Date**: {self.results['timestamp']}\n\n")

            # Pipeline summary
            if (
                self.results.get("pipeline")
                and self.results["pipeline"].get("target_rows") is not None
            ):
                f.write("## Pipeline Performance\n\n")
                p = self.results["pipeline"]
                f.write(f"- **Target rows**: {p['target_rows']:,}\n")
                f.write(f"- **Generated rows**: {p['generated_rows']:,}\n")
                f.write(
                    f"- **Final DB size**: {p['normalization']['final_db_size_mb']:.1f} MB\n"
                )
                f.write(
                    f"- **Data generation**: {p['data_generation']['elapsed_seconds']:.1f}s\n"
                )
                f.write(
                    f"- **Normalization**: {p['normalization']['elapsed_seconds']:.1f}s\n"
                )
                total_pipeline = (
                    p["data_generation"]["elapsed_seconds"]
                    + p["normalization"]["elapsed_seconds"]
                )
                f.write(f"- **Total pipeline**: {total_pipeline:.1f}s\n\n")

            # Query summary
            if self.results["queries"]:
                f.write("## Query Performance\n\n")
                f.write("| Query | Time | Index Used |\n")
                f.write("|-------|------|------------|\n")
                for q in self.results["queries"]:
                    time_str = (
                        f"{q['elapsed_seconds']:.3f}s"
                        if q["elapsed_seconds"]
                        else "FAIL"
                    )
                    idx_str = (
                        "✓"
                        if q["uses_index"]
                        else "✗"
                        if q["full_scan_warning"]
                        else "?"
                    )
                    f.write(f"| {q['name']} | {time_str} | {idx_str} |\n")
                f.write("\n")

            # HTTP VFS summary
            if "http_vfs" in self.results:
                f.write("## HTTP VFS Efficiency\n\n")
                h = self.results["http_vfs"]
                f.write(f"- **Page size**: {h['page_size']} bytes\n")
                f.write(f"- **DB size**: {h['db_size_mb']:.1f} MB\n")
                f.write(f"- **Total pages**: {h['total_pages']:,}\n")
                f.write(f"- **Avg overhead**: {h['avg_overhead_pct']:.1f}%\n\n")

                if h["avg_overhead_pct"] > 10:
                    f.write(
                        "**⚠️ WARNING**: Transfer overhead >10%. Consider increasing page_size to 4096.\n\n"
                    )

            # Recommendations
            f.write("## Optimization Recommendations\n\n")
            self._write_recommendations(f)

    def _write_recommendations(self, f):
        """Write optimization recommendations based on results."""
        recommendations = []

        # Analyze pipeline timing
        p = self.results.get("pipeline", {})
        if p.get("data_generation") and p.get("normalization"):
            total_time = (
                p["data_generation"]["elapsed_seconds"]
                + p["normalization"]["elapsed_seconds"]
            )
            if total_time > 1800:  # 30 minutes
                recommendations.append("Pipeline exceeds 30 minutes. Consider:")
                recommendations.append(
                    "  - Using multiprocessing for parallel normalization"
                )
                recommendations.append(
                    "  - Batch inserts within transactions (already in use)"
                )
                recommendations.append(
                    "  - Streaming JSON parsing with ijson (already in use)"
                )

            # Check normalization speed
            norm_rate = (
                p["normalization"]["rows_inserted"]
                / p["normalization"]["elapsed_seconds"]
            )
            if norm_rate < 1000:
                recommendations.append(
                    f"Normalization rate: {norm_rate:.0f} rows/sec (slow)"
                )
                recommendations.append("  - Ensure using transactions (already used)")
                recommendations.append(
                    "  - Consider disabling indexes during insert, then recreate"
                )
            else:
                recommendations.append(
                    f"Normalization rate: {norm_rate:.0f} rows/sec (good)"
                )

        # Analyze query performance
        slow_queries = [
            q
            for q in self.results["queries"]
            if q["elapsed_seconds"] and q["elapsed_seconds"] > 1.0
        ]
        if slow_queries:
            recommendations.append(
                f"\n{len(slow_queries)} queries >1s. Index optimization needed:"
            )
            for q in slow_queries:
                if "LIKE" in q["sql"] and "%" in q["sql"]:
                    recommendations.append(
                        f"  - {q['name']}: LIKE pattern may not use index efficiently"
                    )
                else:
                    recommendations.append(f"  - {q['name']}: Consider covering index")

        # Analyze HTTP VFS
        if "http_vfs" in self.results:
            overhead = self.results["http_vfs"]["avg_overhead_pct"]
            if overhead > 15:
                recommendations.append(f"\nHTTP overhead {overhead:.1f}% is high.")
                recommendations.append(
                    "  - Increase page_size from 1024 to 4096 (trade-off: more data per request)"
                )
                recommendations.append("  - Verify browser cache is working")
                recommendations.append("  - Check for redundant queries")
            elif overhead > 10:
                recommendations.append(
                    f"\nHTTP overhead {overhead:.1f}% is acceptable but could improve."
                )
                recommendations.append("  - Consider testing page_size=2048 or 4096")
            else:
                recommendations.append(f"\nHTTP overhead {overhead:.1f}% is excellent.")

        # DB size check
        p_norm = self.results.get("pipeline", {}).get("normalization", {})
        if p_norm.get("final_db_size_mb", 0) > 500:
            recommendations.append(
                "\nDatabase >500MB - may impact HTTP Range efficiency."
            )
            recommendations.append("  - Consider compressing with Zstandard")
            recommendations.append("  - Consider splitting by service/region")

        # Write recommendations
        if recommendations:
            for rec in recommendations:
                f.write(f"{rec}\n")
        else:
            f.write(
                "All metrics within acceptable ranges. No major optimizations needed.\n"
            )


# ==================== MAIN ====================


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark AWS Pricing Static application"
    )
    parser.add_argument(
        "--db",
        default="data/aws_pricing.sqlite3",
        help="Path to database for query benchmarks",
    )
    parser.add_argument(
        "--generate-rows",
        type=int,
        help="Generate synthetic data with target row count",
    )
    parser.add_argument(
        "--output-dir", default="benchmark_results", help="Output directory for results"
    )
    parser.add_argument(
        "--skip-pipeline", action="store_true", help="Skip pipeline benchmark"
    )
    parser.add_argument(
        "--skip-queries", action="store_true", help="Skip query benchmarks"
    )
    parser.add_argument(
        "--skip-http", action="store_true", help="Skip HTTP VFS analysis"
    )
    parser.add_argument(
        "--skip-frontend", action="store_true", help="Skip frontend load analysis"
    )

    args = parser.parse_args()

    runner = BenchmarkRunner(args.output_dir)

    # Pipeline benchmark
    if not args.skip_pipeline:
        runner.benchmark_pipeline(args.db, args.generate_rows)
    else:
        print("\nSkipping pipeline benchmark.")

    # Query benchmark
    if not args.skip_queries:
        runner.benchmark_queries(args.db)
    else:
        print("\nSkipping query benchmark.")

    # HTTP VFS efficiency
    if not args.skip_http:
        runner.benchmark_http_vfs(args.db)
    else:
        print("\nSkipping HTTP VFS analysis.")

    # Frontend load analysis
    if not args.skip_frontend:
        runner.benchmark_frontend_load()
    else:
        print("\nSkipping frontend load analysis.")

    # Save results
    runner.save_results()

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
