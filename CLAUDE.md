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

## Project Terminology
- `<AGD>` is used to refer to a separate AnimeGameData path containing the actual data extracted from the game.

## Project Conventions
- ALWAYS use full import path starting from istorath.
- ALWAYS run things from the root of the repo
- ALWAYS write concise commit message; use bullet points when it's helpful but don't feel obligated to include multiple bullets.

## Code Best Practices
- NEVER re-export symbols from child modules in the parent package
- ALWAYS use modern features as available in Python 3.12
- NEVER import individual symbols from modules and ALWAYS use module-level imports only; exceptions: it is okay to import individual symbols from the typing stdlib package.
- NEVER use TYPE_CHECKING conditional imports
- Write very concise docstring; don't list all args & return values when they are self-explanatory from the function signature and names
- Use the Python walrus operation := when appropriate to simplify code

## Import Conventions
- ALWAYS import istorath.agd.types aliased as agd_types outside istorath.agd; but import is normally as from istorath.agd import types when inside the istorath.agd package.
- ALWAYS use from packaeg.subpackage import module import syntax; e.g. from istorath.agd import processing

## Functional Programming Guidelines
- Pass arguments that are not primary inputs to the function itself but rather toolkit objects (e.g. DataRepo) as kw-only args

## Git Workflow Best Practices
- ALWAYS run precommit separately and added resulted changes before you offer to git commit
