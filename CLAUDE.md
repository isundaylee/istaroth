# Claude Code Project Information

## Project Overview
Istaroth is a pipeline for extracting, cleaning, and structuring textual content from Genshin Impact with the goal of powering a Retrieval-Augmented Generation (RAG) language model capable of answering lore questions about the world of Teyvat.

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
- pyrefly (type checking)
- Standard pre-commit hooks (trailing whitespace, YAML validation, etc.)

### Commands
- Install dependencies: `pip install -r requirements.txt`
- Compile requirements: `pip-compile requirements.in`
- Sync dependencies: `pip-sync requirements.txt`
- Install pre-commit: `pre-commit install`
- Run pre-commit manually: `pre-commit run --all-files`
- Type checking: `pyrefly check`

### Project Structure
```
istaroth/
├── istaroth/           # Main package
│   └── __init__.py
├── requirements.in     # High-level dependencies
├── .pre-commit-config.yaml  # Pre-commit configuration
├── pyproject.toml     # Project configuration and pyrefly settings
└── README.md          # Project documentation
```

## Project Terminology
- `<AGD>` is used to refer to a separate AnimeGameData path containing the actual data extracted from the game.

## Project Conventions
- ALWAYS use full import path starting from istaroth.
- ALWAYS run things from the root of the repo
- ALWAYS write concise commit message; use bullet points when it's helpful but don't feel obligated to include multiple bullets.

## Code Best Practices
- ALWAYS prefer inline Python scripts to temporary script files when possible.
- NEVER re-export symbols from child modules in the parent package
- ALWAYS use modern features as available in Python 3.12
- ALWAYS be strict with error handling and prefer raising exception than falling back to implicit default values
- NEVER import individual symbols from modules and ALWAYS use module-level imports only; exceptions: it is okay to import individual symbols from the typing stdlib package.
- NEVER use TYPE_CHECKING conditional imports
- Write very concise docstring; don't list all args & return values when they are self-explanatory from the function signature and names
- Use the Python walrus operation := when appropriate to simplify code
- ALWAYS prefer using features available on pathlib.Path, e.g. read_text and read_bytes
- ALWAYS use names that start with _ for symbols that are not supposed to be used outside its current module/class/etc.
- ALWAYS prefer pytests as functions, not classes
- ALWAYS prefer one-lines
- ALWAYS avoid intermediate variables that is only used once
- ALWAYS avoid writing obvious comments

## Import Conventions
- ALWAYS import istaroth.agd.types aliased as agd_types outside istaroth.agd; but import is normally as from istaroth.agd import types when inside the istaroth.agd package.
- ALWAYS use from packaeg.subpackage import module import syntax; e.g. from istaroth.agd import processing

## Functional Programming Guidelines
- Pass arguments that are not primary inputs to the function itself but rather toolkit objects (e.g. DataRepo) as kw-only args

## Git Workflow Best Practices
- ALWAYS run precommit separately and added resulted changes before you offer to git commit

## Script Development Guidelines
- ALWAYS include a shebang and make the script executable for files under scripts/

## LangSmith Tracing
The RAG pipeline supports LangSmith tracing for debugging and monitoring. Required environment variables:
- `LANGSMITH_API_KEY`: Your LangSmith API key
- `LANGCHAIN_PROJECT`: Project name (e.g., "istaroth-rag")
- `LANGCHAIN_TRACING_V2`: Set to "true" to enable tracing

Optional environment variables:
- `LANGSMITH_ENDPOINT`: Custom LangSmith endpoint (defaults to https://api.smith.langchain.com)

Tracing is automatically enabled when all required environment variables are set.

## Development Conventions
- ALWAYS invoke pyrefly as `env/bin/pyrefly check`
- ALWAYS invoke python as `env/bin/python`; you can source `.source_me` to get env vars if needed.
