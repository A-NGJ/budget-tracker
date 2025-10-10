#!/bin/bash
set -e

echo "🔍 Running code quality checks..."

echo ""
echo "1️⃣  Running ruff linting..."
ruff check src/ tests/

echo ""
echo "2️⃣  Checking code formatting..."
ruff format src/ tests/ --check

echo ""
echo "3️⃣  Running mypy type checking..."
mypy src/ --strict

echo ""
echo "4️⃣  Running tests..."
pytest tests/ -v

echo ""
echo "✅ All quality checks passed!"
