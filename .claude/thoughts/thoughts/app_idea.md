# App idea

## Description

I want to create a simple CLI application that takes as an input an arbitrary bank statement in CSV format and outputs a standardized CSV file with the following columns:

- Date
- Category
- Amount (DKK)
- Source (bank name)

## Tech stack

Backend:
- Python 3.14

LLM Layer:
- Ollama + LLama 3.2 (1B/3B) - runs locally, privacy-focused, low resource usage

Processing:
- Pandas - CSV manipulation and data transformation
- Pydantic - Data validation for bank statement schema

Interface:
- CLI framework

## Architecture Flow

1. Upload - Parse CSV statements with format detection. Pass the file as an CLI argument.
2. For every standard column, ask user which column in the uploaded CSV corresponds to it.
3. Normalize - Convert to unified schema with Pandas
4. Categorize - Pass transaction descriptions to local LLM via Ollama API
5. Export - Generate unified CSV
