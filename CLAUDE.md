# Claude Code Project Information

## Project Overview
Istorath is a pipeline for extracting, cleaning, and structuring textual content from Genshin Impact with the goal of powering a Retrieval-Augmented Generation (RAG) language model capable of answering lore questions about the world of Teyvat.

## Development Setup

### Requirements Management
This project uses pip-tools for dependency management:
- Main dependencies are listed in `requirements.in`
- Run `pip-compile requirements.in` to generate `requirements.txt`
- Run `pip-sync requirements.txt` to install/sync dependencies

### Code Quality
Pre-commit hooks are configured with:
- Black (code formatting)
- isort (import sorting)
- mypy (type checking)
- Standard pre-commit hooks (trailing whitespace, YAML validation, etc.)

### Commands
- Install dependencies: `pip install -r requirements.txt`
- Compile requirements: `pip-compile requirements.in`
- Sync dependencies: `pip-sync requirements.txt`
- Install pre-commit: `pre-commit install`
- Run pre-commit manually: `pre-commit run --all-files`
- Type checking: `mypy istorath/`

### Project Structure
```
istorath/
├── istorath/           # Main package
│   └── __init__.py
├── requirements.in     # High-level dependencies
├── .pre-commit-config.yaml  # Pre-commit configuration
├── pyproject.toml     # Project configuration and mypy settings
└── README.md          # Project documentation
```