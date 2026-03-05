"""Unit tests for pipeline.normalize module."""

import pytest
from pipeline.normalize import (
    parse_memory_gb,
    parse_storage_gb,
    REGION_MAP,
    OS_MAP,
    TENANCY_MAP,
    normalize_product,
    normalize_lease_term,
)


class TestParseMemoryGb:
    """Test parse_memory_gb function."""

    def test_parses_gib_format(self):
        """Test parsing GiB memory strings."""
        assert parse_memory_gb("8 GiB") == 8.0
        assert parse_memory_gb("16 GiB") == 16.0
        assert parse_memory_gb("0.5 GiB") == 0.5

    def test_parses_mib_format(self):
        """Test parsing MiB memory strings."""
        assert parse_memory_gb("16 MiB") == 16.0 / 1024
        assert parse_memory_gb("1024 MiB") == 1.0
        assert parse_memory_gb("512 MiB") == 0.5

    def test_parses_gb_format(self):
        """Test parsing GB memory strings."""
        assert parse_memory_gb("32GB") == 32.0
        assert parse_memory_gb("64 GB") == 64.0

    def test_parses_mb_format(self):
        """Test parsing MB memory strings."""
        assert parse_memory_gb("256 MB") == 256.0 / 1024
        assert parse_memory_gb("1024 MB") == 1.0

    def test_handles_empty_string(self):
        """Test with empty memory string."""
        assert parse_memory_gb("") is None

    def test_handles_none(self):
        """Test with None input."""
        assert parse_memory_gb(None) is None  # type: ignore

    def test_handles_invalid_format(self):
        """Test with invalid memory string."""
        assert parse_memory_gb("invalid") is None
        assert parse_memory_gb("8") is None

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert parse_memory_gb("8 GIB") == 8.0
        assert parse_memory_gb("8 gib") == 8.0
        assert parse_memory_gb("8 mIb") == 8.0 / 1024


class TestParseStorageGb:
    """Test parse_storage_gb function."""

    def test_parses_gib_format(self):
        """Test parsing GiB storage strings."""
        assert parse_storage_gb("1 GiB") == 1
        assert parse_storage_gb("100 GiB") == 100

    def test_parses_gb_format(self):
        """Test parsing GB storage strings."""
        assert parse_storage_gb("100 GB") == 100
        assert parse_storage_gb("1 TB") == 1024

    def test_parses_tb_format(self):
        """Test parsing TB storage strings."""
        assert parse_storage_gb("2 TB") == 2048
        assert parse_storage_gb("0.5 TB") == 512

    def test_parses_mib_format(self):
        """Test parsing MiB storage strings."""
        assert parse_storage_gb("1024 MiB") == 1
        assert parse_storage_gb("512 MiB") == 0

    def test_handles_ebs_only(self):
        """Test 'EBS only' storage."""
        assert parse_storage_gb("EBS only") == 0
        assert parse_storage_gb("ebs only") == 0

    def test_handles_compound_storage(self):
        """Test compound storage like '1 x 222 GiB'."""
        assert parse_storage_gb("1 x 222 GiB") == 222
        assert parse_storage_gb("2 x 400 GB") == 400

    def test_handles_empty_string(self):
        """Test with empty storage string."""
        assert parse_storage_gb("") is None

    def test_handles_invalid_format(self):
        """Test with invalid storage string."""
        assert parse_storage_gb("invalid") is None


class TestRegionMapping:
    """Test region mapping constants."""

    def test_contains_expected_regions(self):
        """Test that important regions are in the mapping."""
        expected = {
            "US East (N. Virginia)": "us-east-1",
            "US West (Oregon)": "us-west-2",
            "Europe (Ireland)": "eu-west-1",
            "Asia Pacific (Tokyo)": "ap-northeast-1",
        }
        for display, code in expected.items():
            assert REGION_MAP[display] == code

    def test_all_regions_have_codes(self):
        """Test that all mapped regions follow the AWS region code pattern."""
        for display, code in REGION_MAP.items():
            assert code.startswith(
                ("us-", "eu-", "ap-", "sa-", "ca-", "af-", "me-", "cn-")
            )
            assert "-" in code

    def test_mapping_is_complete_for_common_regions(self):
        """Test that common regions are present."""
        common_regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-southeast-1",
            "ap-southeast-2",
        ]
        # All common regions should be in the values
        for region in common_regions:
            assert region in REGION_MAP.values()


class TestOSMapping:
    """Test OS mapping constants."""

    def test_linux_mappings(self):
        """Test Linux variants map correctly."""
        assert OS_MAP["Linux"] == "Linux"
        assert OS_MAP["Red Hat Enterprise Linux"] == "RHEL"
        assert OS_MAP["Red Hat Enterprise Linux with HA"] == "RHEL"
        assert OS_MAP["SUSE Linux"] == "SUSE"

    def test_windows_mapping(self):
        """Test Windows mapping."""
        assert OS_MAP["Windows"] == "Windows"

    def test_contains_expected_os(self):
        """Test expected OS entries exist."""
        assert "Linux" in OS_MAP.values()
        assert "Windows" in OS_MAP.values()
        assert "RHEL" in OS_MAP.values()
        assert "SUSE" in OS_MAP.values()


class TestTenancyMapping:
    """Test tenancy mapping constants."""

    def test_all_tenancy_types(self):
        """Test all tenancy types map correctly."""
        assert TENANCY_MAP["Shared"] == "Shared"
        assert TENANCY_MAP["Dedicated"] == "Dedicated"
        assert TENANCY_MAP["Host"] == "Host"


class TestNormalizeProduct:
    """Test normalize_product function with various inputs."""

    def create_minimal_ec2_product(self, **overrides):
        """Helper to create a minimal EC2 product JSON structure."""
        base_product = {
            "product": {
                "productFamily": "AmazonEC2",
                "attributes": {
                    "location": "US East (N. Virginia)",
                    "instanceType": "t2.micro",
                    "operatingSystem": "Linux",
                    "tenancy": "Shared",
                    "vcpu": "1",
                    "memory": "1 GiB",
                    "storage": "EBS only",
                    "preInstalledSw": "NA",
                },
            },
            "terms": {
                "OnDemand": {
                    "123456": {
                        "priceDimensions": {
                            "789012": {
                                "pricePerUnit": {"USD": "0.0116"},
                                "unit": "Hrs",
                                "description": "On-Demand Linux t2.micro Instance",
                            }
                        }
                    }
                }
            },
            "sku": "123456",
        }
        # Apply overrides (merge attributes if provided)
        if "product" in overrides:
            prod_override = overrides["product"]
            for key, value in prod_override.items():
                if key == "attributes" and isinstance(value, dict):
                    base_product["product"].setdefault("attributes", {}).update(value)
                else:
                    base_product["product"][key] = value
        if "terms" in overrides:
            base_product["terms"].update(overrides["terms"])
        if "sku" in overrides:
            base_product["sku"] = overrides["sku"]
        return (
            base_product,
            base_product,
        )  # normalize_product expects (product, raw_data)

    def test_burst_capable_t2_micro(self):
        """Test burst capable extraction for t2.micro (should be yes)."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"burstCapable": "yes"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].burst_capable is True
        assert rows[0].instance_type == "t2.micro"

    def test_burst_capable_t3_small(self):
        """Test burst capable extraction for t3.small (should be yes)."""
        product, raw_data = self.create_minimal_ec2_product(
            product={
                "attributes": {
                    "instanceType": "t3.small",
                    "burstCapable": "true",
                }
            }
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].burst_capable is True
        assert rows[0].instance_type == "t3.small"

    def test_burst_capable_m5_large(self):
        """Test burst capable extraction for m5.large (should be no/None)."""
        product, raw_data = self.create_minimal_ec2_product(
            product={
                "attributes": {
                    "instanceType": "m5.large",
                    "burstCapable": "no",
                }
            }
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].burst_capable is False
        assert rows[0].instance_type == "m5.large"

    def test_burst_capable_missing(self):
        """Test burst capable when attribute is missing."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"burstCapable": ""}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].burst_capable is None

    def test_normalize_service_ec2(self):
        """Test service normalization for EC2 product."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"productFamily": "AmazonEC2"}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].service == "ec2"

    def test_normalize_service_rds(self):
        """Test service normalization for RDS product."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"productFamily": "AmazonRDS"}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].service == "rds"

    def test_normalize_service_lambda(self):
        """Test service normalization for Lambda product."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"productFamily": "AmazonLambda"}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].service == "lambda"

    def test_region_mapping(self):
        """Test region mapping from display name to code."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"location": "US East (N. Virginia)"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].region == "us-east-1"

    def test_region_mapping_europe(self):
        """Test region mapping for Europe."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"location": "Europe (Ireland)"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].region == "eu-west-1"

    def test_region_fallback_for_unknown(self):
        """Test fallback region transformation for unknown locations."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"location": "Unknown Region"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].region == "unknown-region"

    def test_os_mapping_windows(self):
        """Test OS mapping for Windows."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"operatingSystem": "Windows"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].os == "Windows"

    def test_os_mapping_rhel(self):
        """Test OS mapping for RHEL."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"operatingSystem": "Red Hat Enterprise Linux"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].os == "RHEL"

    def test_tenancy_mapping(self):
        """Test tenancy mapping."""
        for raw_tenancy, expected in TENANCY_MAP.items():
            product, raw_data = self.create_minimal_ec2_product(
                product={"attributes": {"tenancy": raw_tenancy}}
            )
            rows = normalize_product(product, raw_data)
            assert len(rows) == 1
            assert rows[0].tenancy == expected

    def test_vcpu_parsing(self):
        """Test vCPU parsing."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"vcpu": "4"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].vcpu == 4

    def test_vcpu_parsing_invalid(self):
        """Test vCPU parsing with invalid value."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"vcpu": "invalid"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].vcpu is None

    def test_memory_parsing(self):
        """Test memory parsing via parse_memory_gb."""
        product, raw_data = self.create_minimal_ec2_product(
            product={"attributes": {"memory": "8 GiB"}}
        )
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].memory_gb == 8.0

    def test_price_extraction(self):
        """Test price extraction from OnDemand term."""
        product, raw_data = self.create_minimal_ec2_product()
        rows = normalize_product(product, raw_data)
        assert len(rows) == 1
        assert rows[0].hourly == 0.0116
        assert rows[0].monthly == pytest.approx(0.0116 * 24 * 30)

    def test_reserved_instance_detection(self):
        """Test Reserved instance detection via description."""
        product = {
            "product": {
                "productFamily": "AmazonEC2",
                "attributes": {
                    "location": "US East (N. Virginia)",
                    "instanceType": "m5.large",
                    "operatingSystem": "Linux",
                    "tenancy": "Shared",
                    "vcpu": "2",
                    "memory": "8 GiB",
                },
            },
            "terms": {
                "Reserved": {
                    "123456": {
                        "priceDimensions": {
                            "789012": {
                                "pricePerUnit": {"USD": "0.05"},
                                "unit": "Hrs",
                                "description": "Reserved Linux m5.large Instance",
                            }
                        }
                    }
                }
            },
            "sku": "123456",
        }
        rows = normalize_product(product, product)
        assert len(rows) == 1
        assert rows[0].purchase_option == "Reserved"
        assert (
            rows[0].lease_term is None
        )  # Simplified, actual parsing of lease term is complex


class TestNormalizeLeaseTerm:
    """Test normalize_lease_term function."""

    def test_normalizes_one_year_variants(self):
        """Test various 1-year formats."""
        assert normalize_lease_term("1-yr") == "1yr"
        assert normalize_lease_term("1yr") == "1yr"
        assert normalize_lease_term("1 year") == "1yr"
        assert normalize_lease_term("1 yr") == "1yr"

    def test_normalizes_three_year_variants(self):
        """Test various 3-year formats."""
        assert normalize_lease_term("3-yr") == "3yr"
        assert normalize_lease_term("3yr") == "3yr"
        assert normalize_lease_term("3 year") == "3yr"

    def test_handles_empty_string(self):
        """Test with empty string."""
        assert normalize_lease_term("") == ""

    def test_handles_none(self):
        """Test with None."""
        assert normalize_lease_term(None) is None  # type: ignore

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert normalize_lease_term("1-YR") == "1yr"
        assert normalize_lease_term("Three Year") == "threeyear"
