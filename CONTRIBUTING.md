# Contributing to tasksmd-sync

Thank you for your interest in contributing! This project uses a few tools to ensure code quality and consistency.

## Development Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   ```
3. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
4. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Code Quality Tools

We use the following tools to maintain code quality:

- **Ruff:** For linting and formatting.
- **Mypy:** For static type checking.
- **Pytest:** For unit testing.

You can run these locally:

```bash
# Run linter
ruff check .

# Run formatter
ruff format .

# Run type checker
mypy tasksmd_sync/

# Run tests
pytest
```

## Workflow

1. Create a new branch for your feature or bugfix.
2. Ensure all tests pass and there are no linting or type errors.
3. Submit a Pull Request.
4. CI will run all checks automatically on your PR.

## Versioning

This project follows [Semantic Versioning](https://semver.org/). Version tags should be created on the `main` branch.
