#!/bin/bash
set -e

echo "=== Python Coverage ==="
cd pipeline
python -m pytest --cov=pipeline --cov-report=term-missing --cov-report=html
echo "HTML report: file://$(pwd)/htmlcov/index.html"

echo "=== TypeScript Coverage ==="
cd ../frontend
npm run test:coverage --silent || true
echo "HTML report: file://$(pwd)/coverage/lcov-report/index.html"
