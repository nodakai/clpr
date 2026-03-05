#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import click
import logging
import sys
import traceback

# Import pipeline functions
from .download_pricing import download_all
from .normalize import normalize_all
from .generate_db import generate_database


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(ctx, verbose):
    """AWS Pricing data pipeline"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        return
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@cli.command()
def download():
    """Download AWS pricing data"""
    try:
        click.echo("Starting download...")
        download_all()
        click.echo("Download complete!")
    except Exception as e:
        click.echo(f"Download failed: {e}", err=True)
        traceback.print_exc()
        sys.exit(1)


@cli.command()
def normalize():
    """Normalize raw data"""
    try:
        click.echo("Normalizing...")
        normalize_all("data/aws_pricing.sqlite3")
        click.echo("Normalization complete!")
    except Exception as e:
        click.echo(f"Normalization failed: {e}", err=True)
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "--output", "-o", default="data/aws_pricing.sqlite3", help="Output database path"
)
def generate(output):
    """Generate SQLite database"""
    try:
        click.echo("Generating database...")
        generate_database(output)
        click.echo("Database generated!")
    except Exception as e:
        click.echo(f"Database generation failed: {e}", err=True)
        traceback.print_exc()
        sys.exit(1)


@cli.command()
def all():
    """Run full pipeline"""
    try:
        click.echo("Starting full pipeline...")
        download_all()
        click.echo("Download complete!")
        normalize_all("data/aws_pricing.sqlite3")
        click.echo("Normalization complete!")
        generate_database("data/aws_pricing.sqlite3")
        click.echo("Database generated!")
    except Exception as e:
        click.echo(f"Pipeline failed: {e}", err=True)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
