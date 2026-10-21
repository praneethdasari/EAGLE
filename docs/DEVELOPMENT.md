# EAGLE Developer Guide

Welcome to the development guide for **EAGLE** (Enhanced Autonomous General-purpose Local Executive).

---

## 1. Development Environment

Always activate the project virtual environment before working:
```powershell
.\.venv\Scripts\Activate.ps1
```

Verify your active Python path:
```powershell
Get-Command python | Select-Object -ExpandProperty Source
```
It should point inside `EAGLE\.venv\Scripts\python.exe`.

---

## 2. Code Quality & Standards

### Formatting & Linting
We use `ruff` for fast linting and formatting:
```powershell
# Format code
ruff format eagle tests

# Check lint rules
ruff check eagle tests

# Automatically fix fixable issues
ruff check --fix eagle tests
```

### Static Type Checking
We enforce static typing via `mypy`:
```powershell
mypy eagle
```

All new public functions, classes, and methods must have full type annotations.

---

## 3. Running Tests

### Fast Offline Unit Tests
```powershell
pytest
```
For verbose output:
```powershell
pytest -v -s
```

Run a specific test file:
```powershell
pytest tests/unit/test_config.py
```

### Writing New Tests
- Place unit tests under `tests/unit/`.
- Mock all external dependencies (audio hardware, network requests, OS subprocesses).
- Use `pytest-mock` fixtures (`mocker`).
- Ensure unit tests run without internet access or audio devices.

---

## 4. Git Commit & Push Conventions

EAGLE uses **Conventional Commits**:
- `feat: <description>` — New user-facing feature or tool
- `fix: <description>` — Bug fix
- `test: <description>` — Adding or updating tests
- `docs: <description>` — Documentation updates
- `refactor: <description>` — Code reorganization with no functional change
- `chore: <description>` — Dependency updates, build configs

### Mandatory Pre-Commit Checklist
Before committing:
1. Run `pytest` to ensure all tests pass.
2. Run `ruff check eagle tests`.
3. Check `git status` and `git diff` for untracked files or accidental credentials.
4. Update `CHANGELOG.md`, `docs/FEATURE_STATUS.md`, and `docs/TASK_LOG.md`.
5. Stage intended files, commit, and push to GitHub.
