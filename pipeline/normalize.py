"""Normalization module for AWS pricing data.

This module processes raw JSON files downloaded from AWS Price List API
and normalizes them into flat records ready for database insertion.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterator
from pipeline.schema import PriceRow

logger = logging.getLogger(__name__)

# Region mapping from AWS display names to region codes
REGION_MAP = {
    "US East (N. Virginia)": "us-east-1",
    "US East (Ohio)": "us-east-2",
    "US West (N. California)": "us-west-1",
    "US West (Oregon)": "us-west-2",
    "Africa (Cape Town)": "af-south-1",
    "Asia Pacific (Hong Kong)": "ap-east-1",
    "Asia Pacific (Mumbai)": "ap-south-1",
    "Asia Pacific (Osaka)": "ap-northeast-3",
    "Asia Pacific (Seoul)": "ap-northeast-2",
    "Asia Pacific (Singapore)": "ap-southeast-1",
    "Asia Pacific (Sydney)": "ap-southeast-2",
    "Asia Pacific (Tokyo)": "ap-northeast-1",
    "Canada (Central)": "ca-central-1",
    "China (Beijing)": "cn-north-1",
    "China (Ningxia)": "cn-northwest-1",
    "Europe (Frankfurt)": "eu-central-1",
    "Europe (Ireland)": "eu-west-1",
    "Europe (London)": "eu-west-2",
    "Europe (Milan)": "eu-south-1",
    "Europe (Paris)": "eu-west-3",
    "Europe (Stockholm)": "eu-north-1",
    "Middle East (Bahrain)": "me-south-1",
    "South America (São Paulo)": "sa-east-1",
    "AWS GovCloud (US-East)": "us-gov-east-1",
    "AWS GovCloud (US-West)": "us-gov-west-1",
}

# Map for Operating System normalization
OS_MAP = {
    "Linux": "Linux",
    "Windows": "Windows",
    "RHEL": "RHEL",
    "SUSE": "SUSE",
    "Red Hat Enterprise Linux": "RHEL",
    "Red Hat Enterprise Linux with HA": "RHEL",
    "SUSE Linux": "SUSE",
}

# Tenancy mapping
TENANCY_MAP = {
    "Shared": "Shared",
    "Dedicated": "Dedicated",
    "Host": "Host",
}


def parse_memory_gb(memory_str: str) -> Optional[float]:
    """Parse memory string like '8 GiB' to float GB."""
    if not memory_str:
        return None
    match = re.match(r"([\d.]+)\s*(GiB|MiB|GB|MB)", memory_str, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit in ("mib", "mb"):
        value /= 1024
    return value


def parse_storage_gb(storage_str: str) -> Optional[int]:
    """Parse storage string to GB integer."""
    if not storage_str:
        return None
    # Handle cases like "1 x 222 GiB" or "EBS only"
    if "ebs" in storage_str.lower() or "only" in storage_str.lower():
        return 0
    # Match decimal numbers for storage size
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(GiB|GB|MiB|MB|TB)", storage_str, re.IGNORECASE
    )
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit in ("mib", "mb"):
        value = value / 1024
    elif unit == "tb":
        value = value * 1024
    # GiB and GB are already in GB, no conversion needed
    return int(round(value))


def normalize_lease_term(lease_term: str) -> str:
    """Normalize lease term string to canonical format.

    Converts variations like "1-yr", "1 year", "1yr" all to "1yr".
    Handles empty or None inputs by returning as-is.

    Args:
        lease_term: Raw lease term string from AWS data.

    Returns:
        Normalized lease term (e.g., "1-yr" -> "1yr", "3 year" -> "3yr").
    """
    if not lease_term:
        return lease_term
    # Remove spaces and hyphens, convert to lowercase
    term = lease_term.lower().replace(" ", "").replace("-", "")
    # If term matches pattern: digits followed by 'year' or 'years', convert to 'yr'
    match = re.match(r"^(\d+)year[s]?$", term)
    if match:
        return f"{match.group(1)}yr"
    # Otherwise return as is (e.g., "1yr", "threeyear")
    return term


def extract_price_dimensions(terms: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract price dimensions from terms structure."""
    price_dimensions = []

    for term in terms.values():
        for term_dimension in term.get("termDimensions", {}).values():
            price_dimensions.append(
                {
                    "rateCode": term_dimension.get("rateCode"),
                    "pricePerUnit": term_dimension.get("priceDimensions", {})
                    .get("pricePerUnit", {})
                    .get("USD"),
                    "unit": term_dimension.get("priceDimensions", {}).get("unit"),
                    "description": term_dimension.get("priceDimensions", {}).get(
                        "description", ""
                    ),
                }
            )
        # Also check direct priceDimensions in term offers
        for sku_key, sku_value in term.items():
            if isinstance(sku_value, dict) and "priceDimensions" in sku_value:
                for pd_key, pd_value in sku_value["priceDimensions"].items():
                    price_dimensions.append(
                        {
                            "rateCode": pd_value.get("rateCode"),
                            "pricePerUnit": pd_value.get("pricePerUnit", {}).get("USD"),
                            "unit": pd_value.get("unit"),
                            "description": pd_value.get("description", ""),
                        }
                    )

    return price_dimensions


def normalize_product(
    product: Dict[str, Any], raw_data: Optional[Dict[str, Any]] = None
) -> List[PriceRow]:
    """Normalize a single AWS product into one or more PriceRow records.

    Returns a list because one product can have multiple pricing options.
    """
    rows = []
    product_attrs = product.get("product", {}).get("attributes", {})
    terms = product.get("terms", {})

    # Extract basic attributes
    product_obj = product.get("product", {})
    service_code = product_obj.get("productFamily", "")
    service = service_code.replace("Amazon", "").lower() if service_code else ""

    # Map region
    region_display = product_attrs.get("location", "")
    region = REGION_MAP.get(region_display, region_display.lower().replace(" ", "-"))

    instance_type = product_attrs.get("instanceType", "")
    instance_family = product_attrs.get("instanceFamily", "")

    os_raw = product_attrs.get("operatingSystem", "")
    os = OS_MAP.get(os_raw, os_raw)

    tenancy_raw = product_attrs.get("tenancy", "")
    tenancy = TENANCY_MAP.get(tenancy_raw, tenancy_raw)

    # Hardware specs
    vcpu = product_attrs.get("vcpu")
    if vcpu is not None:
        try:
            vcpu = int(vcpu)
        except (ValueError, TypeError):
            vcpu = None

    memory_gb = parse_memory_gb(product_attrs.get("memory", ""))

    storage = product_attrs.get("storage", "")
    storage_gb = parse_storage_gb(storage)
    storage_type = product_attrs.get("storageMedia", "")

    network_performance = product_attrs.get("networkPerformance", "")
    processor = product_attrs.get("physicalProcessor", "")

    burst_capable_raw = product_attrs.get("burstCapable", "")
    burst_capable = (
        burst_capable_raw.lower() in ("yes", "true") if burst_capable_raw else None
    )

    gpu = product_attrs.get("gpu")
    if gpu is not None:
        try:
            gpu = int(gpu)
        except (ValueError, TypeError):
            gpu = 0
    else:
        gpu = 0

    gpu_memory_gb = parse_memory_gb(product_attrs.get("gpuMemory", ""))

    sku = product.get("sku", "")

    # Process each term type (OnDemand, Reserved, etc.)
    for term_type, term_dict in terms.items():
        for term_id, term_data in term_dict.items():
            price_dims = term_data.get("priceDimensions", {})

            # Extract term-level metadata (for Reserved)
            term_attrs = term_data  # may contain purchaseOption, offeringClass
            purchase_option_reserved = term_attrs.get("purchaseOption")
            offering_class = term_attrs.get("offeringClass")

            # Normalize purchase_option_reserved: e.g., "All Upfront" -> "AllUpfront"
            if purchase_option_reserved:
                purchase_option_reserved = purchase_option_reserved.replace(" ", "")

            # For Reserved, we aggregate; for OnDemand, we create one row per dimension
            if term_type == "Reserved":
                upfront_total = 0.0
                hourly_price = None

                for pd_key, pd_value in price_dims.items():
                    price_per_unit = pd_value.get("pricePerUnit", {}).get("USD")
                    if price_per_unit is None:
                        continue
                    try:
                        price_val = float(price_per_unit)
                    except (ValueError, TypeError):
                        continue

                    unit = pd_value.get("unit", "")
                    desc = pd_value.get("description", "").lower()

                    # Sum all Quantity dimensions with "upfront" in description
                    if unit == "Quantity" and "upfront" in desc:
                        upfront_total += price_val

                    # Capture hourly from Hrs/Hr/Hour
                    if unit in ("Hrs", "Hours", "Hour"):
                        hourly_price = price_val

                hourly = hourly_price
                monthly = hourly * 24 * 30 if hourly is not None else None

                row = PriceRow(
                    service=service,
                    region=region,
                    instance_type=instance_type,
                    family=instance_family,
                    size=None,
                    vcpu=vcpu,
                    memory_gb=memory_gb,
                    storage=storage,
                    storage_gb=storage_gb,
                    storage_type=storage_type,
                    network_performance=network_performance,
                    processor=processor,
                    burst_capable=burst_capable,
                    gpu=gpu,
                    gpu_memory_gb=gpu_memory_gb,
                    os=os,
                    tenancy=tenancy,
                    price_unit=None,
                    purchase_option="Reserved",
                    lease_term=None,  # Could be extracted from term description/attrs
                    purchase_option_reserved=purchase_option_reserved,
                    offering_class=offering_class,
                    hourly=hourly,
                    monthly=monthly,
                    upfront_cost=upfront_total if upfront_total > 0 else None,
                    effective_date=None,
                    sku=sku,
                    rate_code=None,
                )
                rows.append(row)
            else:
                # OnDemand or other term types: one row per price dimension
                for pd_key, pd_value in price_dims.items():
                    price_per_unit = pd_value.get("pricePerUnit", {}).get("USD")
                    hourly = None
                    if price_per_unit is not None:
                        try:
                            hourly = float(price_per_unit)
                        except (ValueError, TypeError):
                            hourly = None

                    monthly = hourly * 24 * 30 if hourly is not None else None

                    row = PriceRow(
                        service=service,
                        region=region,
                        instance_type=instance_type,
                        family=instance_family,
                        size=None,
                        vcpu=vcpu,
                        memory_gb=memory_gb,
                        storage=storage,
                        storage_gb=storage_gb,
                        storage_type=storage_type,
                        network_performance=network_performance,
                        processor=processor,
                        burst_capable=burst_capable,
                        gpu=gpu,
                        gpu_memory_gb=gpu_memory_gb,
                        os=os,
                        tenancy=tenancy,
                        price_unit=pd_value.get("unit"),
                        purchase_option=term_type,
                        lease_term=None,
                        purchase_option_reserved=None,
                        offering_class=None,
                        hourly=hourly,
                        monthly=monthly,
                        upfront_cost=None,
                        effective_date=None,
                        sku=sku,
                        rate_code=pd_value.get("rateCode"),
                    )
                    rows.append(row)

    return rows


def read_raw_json_files(raw_dir: Path) -> Iterator[Dict[str, Any]]:
    """Yield raw JSON objects from data/raw directory."""
    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_dir}")

    json_files = list(raw_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in: {raw_dir}")

    logger.info(f"Found {len(json_files)} raw JSON files")

    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"Loaded {json_file.name}: contains {len(data)} products")
                yield data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {json_file}: {e}")
            continue


def normalize_all(output_path: str | Path) -> None:
    """Normalize all raw pricing data and populate SQLite database.

    Args:
        output_path: Path where the SQLite database will be created.
    """
    import sqlite3
    from pipeline.schema import initialize_database

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Normalizing data and creating database at {output_path}")

    # Connect to SQLite database using context manager
    with sqlite3.connect(output_path) as conn:
        # Initialize schema
        initialize_database(conn)

        # Process each raw JSON file
        raw_dir = Path("data/raw")
        total_rows_inserted = 0

        for raw_data in read_raw_json_files(raw_dir):
            # raw_data is a list of product items
            logger.info(f"Processing {len(raw_data)} products")

            for product in raw_data:
                try:
                    rows = normalize_product(product)
                    for row in rows:
                        # Insert row into database
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
                        total_rows_inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to normalize product: {e}")
                    continue

            conn.commit()
            logger.info(f"Total rows inserted so far: {total_rows_inserted}")

        logger.info(
            f"Normalization complete. Total rows inserted: {total_rows_inserted}"
        )
