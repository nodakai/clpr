# AWS Pricing Data Pipeline

Python-based pipeline for downloading, normalizing, and generating a SQLite database from AWS Price List API data.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the pipeline as a module:

```bash
python -m pipeline [COMMAND]
```

Or after installing dependencies, make executable:

```bash
chmod +x __main__.py
./__main__.py [COMMAND]
```

### Commands

- `download` - Download raw AWS pricing data via boto3
- `normalize` - Transform raw JSON into normalized format
- `generate` - Create SQLite database with proper schema and indexes
- `all` - Run the complete pipeline (download → normalize → generate)

## Output

Generated SQLite database will be placed in `data/aws_pricing.sqlite3` (relative to project root).