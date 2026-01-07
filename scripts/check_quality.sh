#!/bin/bash
set -e

echo "🔍 Running code quality checks..."

echo ""
echo "1️⃣  Running ruff linting..."
uv run ruff check src/ tests/

echo ""
echo "2️⃣  Checking code formatting..."
uv run ruff format src/ tests/ --check

echo ""
echo "3️⃣  Runningty type checking..."
uv run ty check src/

echo ""
echo "4️⃣  Running tests..."
uv run pytest tests/ -v

echo ""
echo "✅ All quality checks passed!"
