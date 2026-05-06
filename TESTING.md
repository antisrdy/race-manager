# Testing Guide

This project uses **pytest** for testing. The test suite covers database operations, API endpoints, and utility functions.

## Test Structure

- **tests/conftest.py** - Pytest fixtures and configuration
- **tests/test_database.py** - Database schema and integrity tests
- **tests/test_app.py** - Flask application integration tests
- **tests/test_utils.py** - Utility function unit tests
- **tests/fixtures/test_data_english.csv** - Sample test data with English headers
- **tests/fixtures/test_data_french.csv** - Sample test data with French headers

## Running Tests

### Install Test Dependencies

First, install the development dependencies:

```bash
pip install -e ".[dev]"
```

Or install pytest directly:

```bash
pip install pytest
```

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test Files

```bash
pytest tests/test_database.py
pytest tests/test_app.py
pytest tests/test_utils.py
```

### Run Specific Test Classes or Functions

```bash
# Run a specific test class
pytest tests/test_app.py::TestCheckIn

# Run a specific test function
pytest tests/test_app.py::TestCheckIn::test_toggle_checkin
```

### Run Tests with Coverage

Install pytest-cov:

```bash
pip install pytest-cov
```

Then run:

```bash
pytest --cov=. --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Run Tests in Parallel

Install pytest-xdist:

```bash
pip install pytest-xdist
```

Then run:

```bash
pytest -n auto
```

## Test Coverage

The test suite covers:

### Database Tests (test_database.py)
- ✅ Schema initialization and migration
- ✅ Table structure validation
- ✅ Foreign key constraints
- ✅ Unique constraints (bib numbers, finish times)
- ✅ Cascade deletion
- ✅ Default values

### Application Tests (test_app.py)
- ✅ Health check endpoint
- ✅ Home page and race listing
- ✅ Race management (create, update, delete)
- ✅ Runner import (CSV/Excel, English/French formats)
- ✅ Check-in functionality
- ✅ Finish line logging
- ✅ Finish time editing and deletion
- ✅ Ranking and results
- ✅ Database connection management

### Utility Tests (test_utils.py)
- ✅ Elapsed time calculation
- ✅ Data normalization (French/English columns)
- ✅ File parsing (CSV/Excel)
- ✅ Edge cases and error handling

## Test Data

Sample test data files are provided:
- `test_data_english.csv` - Runners with English column headers (bib_number, name, race)
- `test_data_french.csv` - Runners with French column headers (DOSSARD, NOM, PRENOM, DISTANCE)

These can be used for manual testing of the import functionality.

## Continuous Integration

The project includes a GitHub Actions workflow that automatically runs tests on every push and pull request.

### Workflow Configuration

The workflow is defined in `.github/workflows/ci.yml` and:
- Runs on Python 3.10, 3.11, and 3.12 to ensure compatibility
- Installs all dependencies including test requirements
- Executes the full pytest test suite
- Verifies the application imports correctly
- Also builds the Docker image to ensure it's valid

### Status Badge

Add this badge to your README.md to show CI status:

```markdown
![CI](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)
```

### Local Testing Before Push

To ensure tests pass before pushing:

```bash
# Run the same tests as CI
pytest -v --tb=short

# Or run with coverage
pytest --cov=. --cov-report=term-missing
```

## Writing New Tests

### Test Fixtures

Common fixtures are available in `tests/conftest.py`:
- `temp_db` - Temporary database file
- `db` - Database connection
- `app` - Flask application instance
- `client` - Test client for making requests
- `sample_race` - Pre-created race
- `sample_runners` - Pre-created runners

### Example Test

```python
def test_my_feature(client, sample_race):
    """Test description."""
    response = client.get(f'/races/{sample_race["id"]}')
    assert response.status_code == 200
    assert b'expected content' in response.data
```

## Troubleshooting

### Database Lock Errors

If you encounter database lock errors, ensure:
1. All connections are properly closed
2. Tests are not running in parallel with file system conflicts
3. The WAL mode is enabled (done automatically)

### Import Errors

If imports fail, ensure:
1. The package is installed in development mode: `pip install -e .`
2. You're running tests from the project root directory

### Failed Tests

For debugging failed tests:

```bash
# Show full traceback
pytest --tb=long

# Stop at first failure
pytest -x

# Drop into debugger on failure
pytest --pdb
```
