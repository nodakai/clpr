import boto3
import botocore
import ijson
import json
import logging
import os
import sys
from botocore.config import Config
from tqdm import tqdm
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Target AWS services to download pricing for
TARGET_SERVICES = [
    "AmazonEC2",
    "AmazonRDS",
    "AmazonLambda",
    "AmazonS3",
    "AmazonElastiCache",
    "AmazonRedshift",
    "AmazonOpenSearchService",
]

# Output directory for raw JSON files
RAW_DATA_DIR = Path("data/raw")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def create_pricing_client():
    """Create boto3 pricing client with retry configuration."""
    config = Config(
        region_name="us-east-1", retries={"max_attempts": 5, "mode": "adaptive"}
    )
    return boto3.client("pricing", config=config)


def download_service_pricing(client, service_name, filters=None):
    """Download pricing data for a single service using pagination and streaming.

    Args:
        client: Boto3 pricing client
        service_name: Service code (e.g., 'AmazonEC2')
        filters: Optional list of filter dicts to pass to the API. Defaults to us-east-1 region filter.

    Returns:
        bool: True if successful
    """
    if filters is None:
        filters = [{"Type": "TERM_MATCH", "Field": "regionCode", "Value": "us-east-1"}]

    output_file = RAW_DATA_DIR / f"{service_name}.json"

    try:
        logger.info(f"Starting download for {service_name}")

        # Use paginator to handle large result sets
        paginator = client.get_paginator("get_products")

        page_count = 0
        total_items = 0

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "wb") as f:
            # Write opening bracket for JSON array
            f.write(b"[")

            first_item = True
            page_iterator = paginator.paginate(
                ServiceCode=service_name,
                FormatVersion="aws_v1",
                Filters=filters,
            )

            for page in tqdm(
                page_iterator, desc=f"Downloading {service_name}", unit="page"
            ):
                page_count += 1

                # The page contains 'PriceList' which is a list of JSON strings
                for price_item_str in page.get("PriceList", []):
                    total_items += 1

                    # Parse the JSON string to validate and re-serialize
                    try:
                        price_item = json.loads(price_item_str)

                        # Add comma separator if not first item
                        if not first_item:
                            f.write(b",")
                        else:
                            first_item = False

                        # Write compact JSON
                        f.write(
                            json.dumps(price_item, separators=(",", ":")).encode(
                                "utf-8"
                            )
                        )
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"{service_name}: Failed to parse price item: {e}"
                        )
                        continue

            # Write closing bracket for JSON array
            f.write(b"]")

        logger.info(
            f"Completed {service_name}: {total_items} items across {page_count} pages"
        )
        return True

    except botocore.exceptions.ClientError as e:
        logger.error(f"ClientError for {service_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error for {service_name}: {e}")
        return False


def download_ec2_us_east_1_only():
    """Download only EC2 data for us-east-1 region (small test dataset).

    Backward compatibility wrapper for removed download_filtered.py.
    """
    client = create_pricing_client()
    filters = [{"Type": "TERM_MATCH", "Field": "regionCode", "Value": "us-east-1"}]
    return download_service_pricing(client, "AmazonEC2", filters=filters)


def download_all():
    """Download pricing data for all target services."""
    logger.info("Starting AWS pricing data download")

    # Create the client
    client = create_pricing_client()

    # Track results
    success_count = 0
    failure_count = 0

    # Download each service
    for service in TARGET_SERVICES:
        success = download_service_pricing(client, service)
        if success:
            success_count += 1
        else:
            failure_count += 1

    logger.info(f"Download complete: {success_count} succeeded, {failure_count} failed")


if __name__ == "__main__":
    download_all()
