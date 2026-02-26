# Race Manager

A lightweight web application for managing running races: import runners, track check-in, log finish times at a shared finish line, and display rankings by elapsed time.

---

## Quick start (local development)

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** in your browser.

The SQLite database (`race_manager.db`) is created automatically on first run.

> **Reset all data:** stop the server, delete `race_manager.db`, and restart.

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

## File structure

```
race-manager/
├── app.py                  # Flask application
├── database.py             # SQLite schema & initialisation
├── requirements.txt
├── gunicorn.conf.py        # Gunicorn production settings
├── Dockerfile
├── docker-compose.yml
├── .env.example            # Environment variable template
├── sample_runners.csv      # Example import file
├── static/
│   └── style.css
└── templates/
    ├── base.html           # Shared layout + navbar
    ├── index.html          # Home — import + race list
    ├── race.html           # Race detail — runner list
    ├── checkin.html        # Centralised check-in
    ├── finish_line.html    # Global finish logging
    └── ranking.html        # Results by race + gender
```

---

## Schema

The SQLite database has three tables:

- **races** — `id`, `name`, `start_time` (nullable), `created_at`
- **runners** — `id`, `race_id`, `bib_number` (globally unique), `name`, `age`, `gender`, `checked_in`
- **finish_times** — `id`, `race_id`, `runner_id`, `bib_number` (globally unique), `finish_time`, `notes`, `logged_at`

The schema version is stored in `PRAGMA user_version`. If the version changes after an upgrade, all tables are dropped and recreated on the next start — **export your data before upgrading**.
