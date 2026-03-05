import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from pipeline.download_pricing import (
    download_service_pricing,
    download_all,
    TARGET_SERVICES,
    RAW_DATA_DIR,
    create_pricing_client,
)


def make_mock_product(sku: str, instance_type: str = "m5.large"):
    """Create a mock AWS product structure."""
    return {
        "product": {
            "productFamily": "AmazonEC2",
            "attributes": {
                "instanceType": instance_type,
                "location": "US East (N. Virginia)",
                "operatingSystem": "Linux",
            },
        },
        "terms": {},
        "sku": sku,
    }


def make_mock_page(products_list):
    """Create a mock paginator page with PriceList containing JSON strings."""
    return {"PriceList": [json.dumps(p) for p in products_list]}


class MockPaginator:
    """Mock paginator that yields pages of PriceList items."""

    def __init__(self, pages):
        self.pages = pages

    def paginate(self, **kwargs):
        return self.pages


@pytest.fixture
def tmp_raw_dir(tmp_path):
    """Create a temporary raw data directory."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    return raw_dir


@pytest.fixture
def mock_client_success():
    """Create a mock boto3 client that returns successful pagination."""
    client = MagicMock()
    paginator = MockPaginator([make_mock_page([make_mock_product("sku1")])])
    client.get_paginator.return_value = paginator
    return client


@pytest.fixture
def mock_client_multiple_pages():
    """Create a mock client with multiple pages."""
    client = MagicMock()
    paginator = MockPaginator(
        [
            make_mock_page([make_mock_product("sku1"), make_mock_product("sku2")]),
            make_mock_page([make_mock_product("sku3")]),
        ]
    )
    client.get_paginator.return_value = paginator
    return client


@pytest.fixture
def mock_client_empty():
    """Create a mock client that returns empty results."""
    client = MagicMock()
    paginator = MockPaginator([make_mock_page([])])
    client.get_paginator.return_value = paginator
    return client


class TestDownloadServicePricing:
    """Tests for download_service_pricing function."""

    def test_writes_file_successfully(self, tmp_raw_dir, mock_client_success):
        """download_service_pricing fetches data and writes JSON file."""
        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            result = download_service_pricing(mock_client_success, "AmazonEC2")

        assert result is True
        output_file = tmp_raw_dir / "AmazonEC2.json"
        assert output_file.exists()

        with open(output_file) as f:
            data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["sku"] == "sku1"
            assert data[0]["product"]["attributes"]["instanceType"] == "m5.large"

    def test_pagination_accumulates_multiple_pages(
        self, tmp_raw_dir, mock_client_multiple_pages
    ):
        """Multiple paginator pages are concatenated correctly."""
        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            result = download_service_pricing(mock_client_multiple_pages, "AmazonEC2")

        assert result is True
        output_file = tmp_raw_dir / "AmazonEC2.json"
        with open(output_file) as f:
            data = json.load(f)
            assert len(data) == 3
            skus = [item["sku"] for item in data]
            assert skus == ["sku1", "sku2", "sku3"]

    def test_handles_empty_response(self, tmp_raw_dir, mock_client_empty):
        """Empty product list handled gracefully."""
        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            result = download_service_pricing(mock_client_empty, "AmazonEC2")

        assert result is True
        output_file = tmp_raw_dir / "AmazonEC2.json"
        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
            assert data == []

    def test_creates_output_directory_if_missing(self, tmp_path, mock_client_success):
        """Creates output directory if it doesn't exist."""
        output_dir = tmp_path / "new_dir"
        assert not output_dir.exists()

        with patch("pipeline.download_pricing.RAW_DATA_DIR", output_dir):
            result = download_service_pricing(mock_client_success, "AmazonEC2")

        assert result is True
        assert output_dir.exists()

    @pytest.mark.skip(
        reason="Retry logic handled by boto3, not at this level; integration test needed."
    )
    def test_retry_on_throttling(self, tmp_raw_dir):
        """Retries on ThrottlingException and eventually succeeds."""
        from botocore.exceptions import ClientError

        call_count = 0

        def create_mock_paginator(service_name):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                paginator = MagicMock()

                def paginate_with_error(**kwargs):
                    raise ClientError(
                        {
                            "Error": {
                                "Code": "ThrottlingException",
                                "Message": "Rate exceeded",
                            }
                        },
                        "GetProducts",
                    )

                paginator.paginate = paginate_with_error
                return paginator
            else:
                return MockPaginator([make_mock_page([make_mock_product("sku1")])])

        mock_client = MagicMock()
        mock_client.get_paginator.side_effect = create_mock_paginator

        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            with patch("time.sleep"):
                result = download_service_pricing(mock_client, "AmazonEC2")

        assert result is True
        assert call_count == 2

    def test_handles_other_client_errors(self, tmp_raw_dir):
        """Other ClientError returns False without retry."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Server error"}},
            "GetProducts",
        )
        mock_client.get_paginator.return_value = paginator

        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            result = download_service_pricing(mock_client, "AmazonEC2")

        assert result is False

    def test_file_is_valid_json_array_format(self, tmp_raw_dir):
        """Output file is properly formatted as JSON array with commas."""
        mock_client = MagicMock()
        paginator = MockPaginator(
            [
                make_mock_page([make_mock_product("sku1"), make_mock_product("sku2")]),
                make_mock_page([make_mock_product("sku3")]),
            ]
        )
        mock_client.get_paginator.return_value = paginator

        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            result = download_service_pricing(mock_client, "AmazonEC2")

        assert result is True
        output_file = tmp_raw_dir / "AmazonEC2.json"
        with open(output_file) as f:
            content = f.read()
            data = json.loads(content)
            assert len(data) == 3

    def test_uses_correct_filters(self, tmp_raw_dir):
        """Download uses correct AWS API filters."""
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = iter([])  # Empty iterator
        mock_client.get_paginator.return_value = paginator

        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            download_service_pricing(mock_client, "AmazonEC2")

        paginator.paginate.assert_called_once()
        call_kwargs = paginator.paginate.call_args[1]
        assert call_kwargs["ServiceCode"] == "AmazonEC2"
        assert call_kwargs["FormatVersion"] == "aws_v1"
        assert len(call_kwargs["Filters"]) == 1
        assert call_kwargs["Filters"][0]["Type"] == "TERM_MATCH"
        assert call_kwargs["Filters"][0]["Field"] == "regionCode"
        assert call_kwargs["Filters"][0]["Value"] == "us-east-1"

    def test_handles_json_decode_error_in_item(self, tmp_raw_dir, caplog):
        """Invalid JSON items are skipped with warning."""
        mock_client = MagicMock()
        paginator = MockPaginator(
            [
                {
                    "PriceList": [
                        json.dumps(make_mock_product("sku1")),
                        "invalid json{",
                        json.dumps(make_mock_product("sku2")),
                    ]
                }
            ]
        )
        mock_client.get_paginator.return_value = paginator

        with patch("pipeline.download_pricing.RAW_DATA_DIR", tmp_raw_dir):
            result = download_service_pricing(mock_client, "AmazonEC2")

        assert result is True
        assert any(
            "Failed to parse price item" in rec.message for rec in caplog.records
        )


class TestDownloadAll:
    """Tests for download_all function."""

    def test_downloads_all_target_services(self, mocker):
        """download_all calls download_service_pricing for each target service."""
        mock_download_service = mocker.patch(
            "pipeline.download_pricing.download_service_pricing", return_value=True
        )
        mock_create_client = mocker.patch(
            "pipeline.download_pricing.create_pricing_client"
        )
        mock_create_client.return_value = MagicMock()

        download_all()

        mock_create_client.assert_called_once()
        assert mock_download_service.call_count == len(TARGET_SERVICES)

    def test_tracks_success_and_failure_counts(self, mocker, caplog):
        """Success and failure counts are tracked and logged."""
        caplog.set_level(logging.INFO)
        mock_download_service = mocker.patch(
            "pipeline.download_pricing.download_service_pricing",
            side_effect=[True, False, True],
        )
        mock_create_client = mocker.patch(
            "pipeline.download_pricing.create_pricing_client"
        )
        mock_create_client.return_value = MagicMock()

        with patch(
            "pipeline.download_pricing.TARGET_SERVICES", ["svc1", "svc2", "svc3"]
        ):
            download_all()

        assert any("Download complete" in rec.message for rec in caplog.records)
        assert any("2 succeeded" in rec.message for rec in caplog.records)
        assert any("1 failed" in rec.message for rec in caplog.records)

    def test_creates_client_once(self, mocker):
        """Creates single client reused for all services."""
        mock_download_service = mocker.patch(
            "pipeline.download_pricing.download_service_pricing", return_value=True
        )
        mock_create_client = mocker.patch(
            "pipeline.download_pricing.create_pricing_client"
        )
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        with patch("pipeline.download_pricing.TARGET_SERVICES", ["svc1", "svc2"]):
            download_all()

        mock_create_client.assert_called_once()
        calls = mock_download_service.call_args_list
        first_client = calls[0][0][0]
        for call in calls:
            assert call[0][0] is first_client

    def test_calls_services_in_order(self, mocker):
        """Services are downloaded in order of TARGET_SERVICES."""
        order = []

        def track_calls(client, service):
            order.append(service)
            return True

        mock_download_service = mocker.patch(
            "pipeline.download_pricing.download_service_pricing",
            side_effect=track_calls,
        )
        mock_create_client = mocker.patch(
            "pipeline.download_pricing.create_pricing_client"
        )
        mock_create_client.return_value = MagicMock()

        download_all()

        assert order == TARGET_SERVICES

    def test_continues_on_failure(self, mocker, caplog):
        """Continues downloading other services even if one fails."""
        caplog.set_level(logging.INFO)
        mock_download_service = mocker.patch(
            "pipeline.download_pricing.download_service_pricing",
            side_effect=[False, True, True],
        )
        mock_create_client = mocker.patch(
            "pipeline.download_pricing.create_pricing_client"
        )
        mock_create_client.return_value = MagicMock()

        with patch(
            "pipeline.download_pricing.TARGET_SERVICES", ["svc1", "svc2", "svc3"]
        ):
            download_all()

        assert mock_download_service.call_count == 3
        assert any("failed" in rec.message for rec in caplog.records)


@pytest.mark.integration
def test_download_service_real_aws(tmp_raw_dir):
    """Integration test with real AWS (requires credentials)."""
    pytest.skip("Integration test skipped by default")
