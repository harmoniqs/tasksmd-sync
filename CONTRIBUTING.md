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

This project follows [Semantic Versioning](https://semver.org/).

### Making a Release

Releases are automated using GitHub Actions. To make a new release:

1. **Prepare Release (Automated):**
   - Go to the **Actions** tab in GitHub.
   - Select the **Prepare Release** workflow.
   - Click **Run workflow**, enter the new version (e.g., `1.2.3`), and run it.
   - This will update `pyproject.toml`, commit the change, and push a new tag `v1.2.3`.

2. **Release (Automated):**
   - The push of the `v*` tag triggers the **Release** workflow.
   - This workflow builds the package and creates a GitHub Release with the built assets.
   - It also updates the corresponding major version tag (e.g., `v1`).

Alternatively, you can manually tag a commit on `main` and push it:
```bash
git tag v1.2.3
git push origin v1.2.3
```
