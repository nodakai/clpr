# Benchmark Tool

Standalone performance benchmarking suite for the AWS Pricing Static application.

This is a self-contained Python tool that measures:
- Pipeline performance (data generation, normalization, database creation)
- Query performance with EXPLAIN analysis
- HTTP VFS efficiency estimates
- Frontend load performance estimates

For complete usage instructions, configuration options, and interpretation of results, see the main documentation:

**[../BENCHMARK_README.md](../BENCHMARK_README.md)**

## Quick Start

```bash
# From project root
cd benchmark
python benchmark.py --db ../data/aws_pricing.sqlite3 --output-dir ../benchmark_results
```

## Notes

- Requires the pipeline modules to be importable (they should be in `../pipeline/`)
- Works with any database following the schema defined in `pipeline/schema.py`
- All results are saved as JSON and Markdown in the output directory