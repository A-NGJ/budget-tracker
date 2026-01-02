#!/bin/bash

# Read JSON input from stdin to get the file path
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip if no file path or not a Python file
if [ -z "$FILE_PATH" ] || [[ ! "$FILE_PATH" == *.py ]]; then
  exit 0
fi

# Skip if file doesn't exist
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

ERRORS=""

# Run ruff format (without fixing)
RUFF_FORMAT_OUTPUT=$(uv run ruff format --check "$FILE_PATH" >/dev/null 2>&1)
RUFF_FORMAT_EXIT=$?
if [ $RUFF_FORMAT_EXIT -ne 0 ]; then
    ERRORS="${ERRORS}Ruff format check failed: File is not properly formatted.
"
fi

# Check for remaining ruff issues
RUFF_OUTPUT=$(uv run ruff check "$FILE_PATH" 2>&1)
RUFF_EXIT=$?
if [ $RUFF_EXIT -ne 0 ]; then
  ERRORS="${ERRORS}Ruff check failed:
${RUFF_OUTPUT}

"
fi

# Run ty on the file
TY_OUTPUT=$(uv run ty check "$FILE_PATH" 2>&1)
TY_EXIT=$?
if [ $T_EXIT -ne 0 ]; then
  ERRORS="${ERRORS}Ty check failed:
${TY_OUTPUT}

"
fi

# Block if errors exist
if [ -n "$ERRORS" ]; then
  ESCAPED_ERRORS=$(echo "$ERRORS" | jq -Rs .)
  echo "{\"decision\": \"block\", \"reason\": $ESCAPED_ERRORS}"
fi

