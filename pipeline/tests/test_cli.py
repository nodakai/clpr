import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from pipeline.__main__ import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    """--help prints usage."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "AWS Pricing data pipeline" in result.output


def test_download_command_success(runner, mocker):
    """download command calls download_all and prints success."""
    mock_download = mocker.patch("pipeline.__main__.download_all", return_value=None)

    result = runner.invoke(cli, ["download"])

    assert result.exit_code == 0
    assert "Download complete!" in result.output
    mock_download.assert_called_once()


def test_normalize_command_success(runner, mocker):
    """normalize command calls normalize_all."""
    mock_normalize = mocker.patch("pipeline.__main__.normalize_all", return_value=None)

    result = runner.invoke(cli, ["normalize"])

    assert result.exit_code == 0
    assert "Normalization complete!" in result.output
    mock_normalize.assert_called_once()


def test_generate_command_success(runner, mocker):
    """generate command calls generate_database."""
    mock_generate = mocker.patch(
        "pipeline.__main__.generate_database", return_value=None
    )

    result = runner.invoke(cli, ["generate"])

    assert result.exit_code == 0
    assert "Database generated!" in result.output
    mock_generate.assert_called_once()


def test_all_command_runs_all(runner, mocker):
    """all command runs download, normalize, generate in sequence."""
    mock_download = mocker.patch("pipeline.__main__.download_all")
    mock_normalize = mocker.patch("pipeline.__main__.normalize_all")
    mock_generate = mocker.patch("pipeline.__main__.generate_database")

    result = runner.invoke(cli, ["all"])

    assert result.exit_code == 0
    mock_download.assert_called_once()
    mock_normalize.assert_called_once()
    mock_generate.assert_called_once()


def test_verbose_flag_sets_debug_logging(runner, mocker):
    """--verbose enables DEBUG logging."""
    mock_logging = mocker.patch("pipeline.__main__.logging.basicConfig")

    result = runner.invoke(cli, ["--verbose", "download"])

    assert result.exit_code == 0
    # Should call basicConfig with level=logging.DEBUG
    mock_logging.assert_called()
    call_kwargs = mock_logging.call_args[1]
    assert call_kwargs.get("level") == 10  # DEBUG level


def test_command_failure_handling(runner, mocker):
    """Exceptions in commands cause non-zero exit and error message."""
    mock_download = mocker.patch(
        "pipeline.__main__.download_all", side_effect=Exception("Network error")
    )

    result = runner.invoke(cli, ["download"])

    assert result.exit_code != 0
    assert "Network error" in result.output or "Error" in result.output


def test_missing_subcommand_shows_help(runner):
    """No arguments shows help."""
    result = runner.invoke(cli, [])
    assert result.exit_code == 0  # click shows help
    assert "Commands:" in result.output


# Optional: Test that output directories are created if missing during all()
# Not needed since we mock the actual work

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
