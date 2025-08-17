# Repository Testing and CI Compliance Guide

This guide provides comprehensive instructions for testing repository functionality and ensuring CI pipeline compliance for Python-based Crossplane functions.

## Prerequisites

Before testing, ensure you have:
- Python 3.11+ installed
- Git repository initialized
- Virtual environment capability
- Access to the repository's CI configuration

## Testing Setup Process

### 1. Environment Preparation

Create and activate a virtual environment in the repository root:

```bash
python3 -m venv .env
source .env/bin/activate  # On Windows: .env\Scripts\activate
```

### 2. Install Build Tools

Install the project's build system (typically hatch for Python projects):

```bash
pip install hatch==1.12.0
```

### 3. Install Project Dependencies

Install the project in development mode with all dependencies:

```bash
pip install -e .
```

If this fails due to Python version constraints, check `pyproject.toml` and update the `requires-python` field to be compatible with your Python version.

## Core Testing Procedures

### 1. Unit Test Execution

Run the complete test suite with randomization:

```bash
hatch test --all --randomize
```

**Expected Outcome**: All tests should pass across all supported Python versions. Look for:
- ✅ `X passed` with no failures
- Tests running on multiple Python versions if available
- No import errors or dependency issues

### 2. Code Quality and Linting

Check and fix code formatting and style issues:

```bash
# Check current state
hatch fmt --check

# Apply fixes automatically  
hatch fmt
```

**Expected Outcome**: 
- `All checks passed!` for the check command
- Automatic formatting applied for style consistency
- No remaining linting errors in main code directories

### 3. Import and Module Structure Validation

Verify that all modules can be imported correctly:

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from function import *
    print('✓ Main function module imports successfully')
except Exception as e:
    print(f'✗ Import failed: {e}')
"
```

## CI Compliance Verification

### 1. Python Version Compatibility

Ensure the project supports the required Python versions by checking `pyproject.toml`:

```toml
requires-python = ">=3.11,<3.14"  # Should be flexible enough
```

### 2. Dependency Resolution

Verify all dependencies install cleanly:

```bash
hatch dep show requirements
pip check  # Verify no dependency conflicts
```

### 3. Test Coverage and Quality

Run tests with coverage if configured:

```bash
hatch test --cover
```

### 4. Build System Validation

Ensure the project can be built and packaged:

```bash
hatch build
```

## Common Issues and Solutions

### Import Errors in Tests

**Problem**: `ModuleNotFoundError` when running tests
**Solution**: 
- Ensure `__init__.py` files exist in all package directories
- Add module-level imports for testability
- Use try/except blocks for relative imports with fallbacks

### Linting Failures

**Problem**: Code style violations (E501, T201, etc.)
**Solution**:
- Run `hatch fmt` to auto-fix formatting
- Break long lines appropriately
- Remove or suppress print statements in production code
- Use consistent indentation and spacing

### Test Failures Due to Mocking

**Problem**: Tests fail because imports happen inside functions
**Solution**:
- Move imports to module level where possible
- Provide fallback imports for direct execution
- Ensure mocked objects match the expected interface

### Python Version Incompatibility

**Problem**: `requires a different Python` error
**Solution**:
- Update `pyproject.toml` to support wider Python version range
- Test with the minimum and maximum supported versions
- Use compatible dependency versions

## Testing Checklist

Before considering the repository CI-compliant, verify:

- [ ] All unit tests pass on supported Python versions
- [ ] Linting passes with no errors in main code directories  
- [ ] All modules can be imported without errors
- [ ] Dependencies install cleanly without conflicts
- [ ] Project builds successfully
- [ ] No critical security or style violations
- [ ] Test coverage meets project standards (if configured)
- [ ] Documentation is up to date with any changes

## Continuous Integration Expectations

A properly configured CI pipeline should:

1. **Install dependencies** cleanly across supported Python versions
2. **Run linting** with zero errors in production code
3. **Execute all tests** with 100% pass rate
4. **Build the project** successfully
5. **Generate artifacts** if applicable (Docker images, packages)

## Best Practices for Maintaining CI Health

1. **Run tests locally** before committing changes
2. **Fix linting issues** immediately when they arise
3. **Keep dependencies updated** and compatible
4. **Monitor test execution time** and optimize slow tests
5. **Maintain consistent code style** across the codebase
6. **Document any special testing requirements** in the repository

## Emergency Debugging

If tests fail unexpectedly:

1. **Check recent changes**: `git log --oneline -10`
2. **Run individual test files**: `python3 -m pytest tests/test_specific.py -v`
3. **Verify environment**: `pip list` and `python3 --version`
4. **Check for import issues**: Test imports in Python REPL
5. **Review CI logs**: Look for specific error messages and stack traces

This guide ensures consistent testing practices and CI compliance across all development environments and team members.
