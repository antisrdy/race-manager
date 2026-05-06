# Race Manager

A lightweight web application for managing running races: import runners, track check-in, log finish times at a shared finish line, and display rankings by elapsed time.

![CI](https://github.com/YOUR_USERNAME/race-manager/actions/workflows/ci.yml/badge.svg)

---

## Quick start (local development)

**Requirements:** Python 3.10+

### 1. Create and activate a virtual environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it (macOS/Linux)
source venv/bin/activate

# Activate it (Windows)
# venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -e .
```

### 3. Run the application

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

The SQLite database (`race_manager.db`) is created automatically on first run.

> **Reset all data:** stop the server, delete `race_manager.db`, and restart.
>
> **Deactivate virtual environment:** run `deactivate` when you're done.

---

## Production deployment (Docker)

**Requirements:** Docker + Docker Compose

### 1. Configure the environment

```bash
cp .env.example .env
```

Edit `.env` and set a strong `SECRET_KEY`:

```bash
# Generate one with:
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Start the app

```bash
docker-compose up -d
```

The app is available at **http://localhost:8000**.

The SQLite database is persisted in the `race_data` Docker named volume — it survives container restarts and upgrades.

### Common operations

```bash
docker-compose logs -f          # stream logs
docker-compose pull && docker compose up -d   # upgrade to a new image
docker-compose down             # stop
docker-compose down -v          # stop and delete all data (irreversible)
```

### Health check

`GET /health` returns `{"status": "ok"}` (HTTP 200) when the app and database are reachable. Docker uses this automatically to monitor the container.

---

## Configuration

All configuration is via environment variables (set in `.env` for Docker, or exported in the shell for local runs).

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `race-manager-dev-secret` | Flask session signing key — **change this in production** |
| `DATABASE` | `race_manager.db` | Path to the SQLite database file |

---

## Workflow

### 1 — Import runners

Prepare a CSV or Excel file with these columns:

| Column | Required | Description |
|---|---|---|
| `bib_number` | yes | Unique integer bib number (globally unique across all races) |
| `name` | yes | Runner's full name |
| `race` | yes | Race name (e.g. `10km`, `21km`, `42km`) — created automatically |
| `age` | no | Runner's age |
| `gender` | no | Gender (e.g. `M`, `F`) — used for gender-split rankings |

A sample file is provided: `sample_runners.csv` (3 races, 21 runners).

On the **Home** page, use the **Import All Runners** button to upload the file. Races are created automatically from the `race` column.

### 2 — Set start times

After import, each race appears on the **Home** page with a **"Set start time"** button. Elapsed times in the ranking are computed as `finish_time − start_time`.

### 3 — Check-in runners

Use the **Check-in** page to mark runners as present. Toggle individually or use **Check In All** per race or globally.

### 4 — Log finish times

Open the **Finish Line** page. Enter a bib number and press Enter. The system automatically detects which race the runner belongs to.

- The **Finish Time** field auto-updates to the current time every second.
- Typing stops the auto-update (useful for logging late entries). Click **Now** to resume.
- Edit or delete logged times with the pencil/trash icons in the table.

### 5 — View rankings

The **Ranking** page shows results per race, sorted by elapsed time. Filter by gender with the pills (Overall / M / F / …). The page auto-refreshes every 30 seconds.

---

## Testing

The project includes a comprehensive test suite with 65 tests covering database operations, API endpoints, and utility functions.

### Running tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_database.py
pytest tests/test_app.py
pytest tests/test_utils.py

# Run with coverage report
pytest --cov=. --cov-report=html
```

### Test coverage

- **Database tests** (test_database.py): Schema, constraints, migrations
- **Application tests** (test_app.py): All endpoints, import, check-in, finish line, ranking
- **Utility tests** (test_utils.py): Time calculations, data normalization, file parsing

See [TESTING.md](TESTING.md) for detailed testing documentation and [TEST_SUMMARY.md](TEST_SUMMARY.md) for current test status.

---

## File structure

```
race-manager/
├── app.py                  # Flask application
├── database.py             # SQLite schema & initialisation
├── gunicorn.conf.py        # Gunicorn production settings
├── pyproject.toml          # Project configuration
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example            # Environment variable template
├── sample_runners.csv      # Example import file
├── README.md
├── TESTING.md              # Testing guide
├── TEST_SUMMARY.md         # Test status summary
├── static/
│   └── style.css
├── templates/
│   ├── base.html           # Shared layout + navbar
│   ├── index.html          # Home — import + race list
│   ├── race.html           # Race detail — runner list
│   ├── checkin.html        # Centralised check-in
│   ├── finish_line.html    # Global finish logging
│   └── ranking.html        # Results by race + gender
└── tests/
    ├── conftest.py         # Pytest fixtures
    ├── test_app.py         # Application integration tests
    ├── test_database.py    # Database tests
    ├── test_utils.py       # Utility function tests
    └── fixtures/
        ├── test_data_english.csv   # Test data (English headers)
        └── test_data_french.csv    # Test data (French headers)
```

---

## Schema

The SQLite database has three tables:

- **races** — `id`, `name`, `start_time` (nullable), `created_at`
- **runners** — `id`, `race_id`, `bib_number` (globally unique), `name`, `age`, `gender`, `checked_in`
- **finish_times** — `id`, `race_id`, `runner_id`, `bib_number` (globally unique), `finish_time`, `notes`, `logged_at`

The schema version is stored in `PRAGMA user_version`. If the version changes after an upgrade, all tables are dropped and recreated on the next start — **export your data before upgrading**.
