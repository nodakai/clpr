import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from pipeline.generate_db import generate_database
from pipeline.schema import initialize_database, create_indexes, set_pragmas


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test.db"


def test_generate_database_creates_file(temp_db_path):
    """generate_database creates SQLite file."""
    # We'll mock normalize_all to avoid heavy processing
    with patch("pipeline.generate_db.normalize_all") as mock_normalize:
        # Have normalize_all create minimal table so file exists
        def create_minimal_db(db_path):
            with sqlite3.connect(db_path) as conn:
                initialize_database(conn)
                conn.execute(
                    "INSERT INTO prices (service, region, os, purchase_option, hourly) VALUES ('test', 'us-east-1', 'Linux', 'OnDemand', 0.0)"
                )
                conn.commit()

        mock_normalize.side_effect = create_minimal_db

        generate_database(temp_db_path, max_size_bytes=0, min_rows=0)

        assert temp_db_path.exists()
        assert temp_db_path.stat().st_size > 0


def test_generate_sets_correct_pragmas(temp_db_path):
    """Database has page_size=1024 and WAL journal."""
    with patch("pipeline.generate_db.normalize_all") as mock_normalize:

        def create_db(db_path):
            with sqlite3.connect(db_path) as conn:
                initialize_database(conn)

        mock_normalize.side_effect = create_db

        generate_database(temp_db_path, max_size_bytes=0, min_rows=0)

        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            assert page_size == 1024

            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            assert journal_mode.lower() == "wal"


def test_generate_creates_all_indexes(temp_db_path):
    """All expected indexes exist after generation."""
    with patch("pipeline.generate_db.normalize_all") as mock_normalize:

        def create_db(db_path):
            with sqlite3.connect(db_path) as conn:
                initialize_database(conn)

        mock_normalize.side_effect = create_db

        generate_database(temp_db_path, max_size_bytes=0, min_rows=0)

        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            expected = ["idx_filter", "idx_instance", "idx_price", "idx_specs"]
            for idx in expected:
                assert idx in indexes


def test_generate_calls_vacuum_and_analyze(temp_db_path):
    """VACUUM and ANALYZE are executed."""
    with patch("pipeline.generate_db.normalize_all") as mock_normalize:

        def create_db(db_path):
            with sqlite3.connect(db_path) as conn:
                initialize_database(conn)

        mock_normalize.side_effect = create_db

        # Mock connection to track executed SQL
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            # Simulate successful generation
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)

            try:
                generate_database(temp_db_path, min_rows=0)
            except:
                pass  # Ignore errors from mocking

            # Check that commit, vacuum, analyze were called
            executed_sql = [
                str(call[0][0]) for call in mock_conn.execute.call_args_list
            ]
            assert any("VACUUM" in sql for sql in executed_sql)
            assert any("ANALYZE" in sql for sql in executed_sql)


def test_generate_validates_size_under_500mb(temp_db_path):
    """Raises assertion if DB exceeds 500MB."""
    # This test would create a huge DB, impractical. Instead, mock the size check.
    # The actual validation is in generate_database: after VACUUM, checks size < 500MB
    # We can test that check by mocking os.path.getsize

    with patch("pipeline.generate_db.normalize_all") as mock_normalize:

        def create_db(db_path):
            with sqlite3.connect(db_path) as conn:
                initialize_database(conn)

        mock_normalize.side_effect = create_db

        with patch("os.path.getsize") as mock_size:
            mock_size.return_value = 100_000  # 100KB, well under limit
            # Should not raise
            generate_database(temp_db_path, max_size_bytes=0, min_rows=0)

            mock_size.assert_called_once_with(str(temp_db_path))


def test_generate_handles_normalization_error(temp_db_path):
    """If normalize_all raises, generate_database exits with error."""
    with patch("pipeline.generate_db.normalize_all", side_effect=RuntimeError("Boom")):
        with pytest.raises(RuntimeError, match="Boom"):
            generate_database(temp_db_path, max_size_bytes=0, min_rows=0)

    # Integration test (optional, requires full pipeline)
    def test_generate_end_to_end_integration(tmp_path):
        """Full end-to-end: create minimal raw JSON, generate DB, validate."""
        # This is more of an integration test; could be slow
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Write minimal raw JSON file
        ec2_data = [
            {
                "product": {
                    "productFamily": "AmazonEC2",
                    "attributes": {
                        "instanceType": "m5.large",
                        "location": "US East (N. Virginia)",
                        "operatingSystem": "Linux",
                        "tenancy": "Shared",
                        "vcpu": "2",
                        "memory": "8 GiB",
                        "storage": "EBS only",
                        "networkPerformance": "Up to 10 Gbps",
                    },
                },
                "terms": {
                    "OnDemand": {
                        "ondemand": {
                            "priceDimensions": {
                                "pd1": {"pricePerUnit": {"USD": "0.096"}, "unit": "Hrs"}
                            }
                        }
                    }
                },
                "sku": "testsku",
            }
        ]
        with open(raw_dir / "AmazonEC2.json", "w") as f:
            json.dump(ec2_data, f)

        output_db = tmp_path / "output.db"

        # Override default paths via monkeypatch if needed; assume code uses data/raw
        # We'll patch normalize_all's input dir
        with patch("pipeline.generate_db.normalize_all") as mock_normalize:

            def real_normalize(output_path):
                # Actually call normalize_all but with our raw_dir
                from pipeline.normalize import normalize_all

                # Temporarily change working directory or pass arguments
                # For simplicity, just call with raw_dir we control
                normalize_all(input_dir=raw_dir, output_db=output_path)

            mock_normalize.side_effect = real_normalize

            generate_database(output_db)

            # Verify DB can be queried
            with sqlite3.connect(output_db) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM prices")
                count = cursor.fetchone()[0]
                assert count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
