"""Tests for database initialization and schema."""
import sqlite3
import pytest
from database import init_db, SCHEMA_VERSION


def test_database_initialization(temp_db):
    """Test that the database is initialized with correct schema."""
    init_db()
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Check schema version
    version = cursor.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION
    
    # Check that all tables exist
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    
    assert 'races' in tables
    assert 'runners' in tables
    assert 'finish_times' in tables
    
    conn.close()


def test_races_table_schema(db):
    """Test races table has correct columns."""
    cursor = db.execute("PRAGMA table_info(races)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    assert 'id' in columns
    assert 'name' in columns
    assert 'start_time' in columns
    assert 'created_at' in columns
    assert columns['name'] == 'TEXT'


def test_runners_table_schema(db):
    """Test runners table has correct columns."""
    cursor = db.execute("PRAGMA table_info(runners)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    assert 'id' in columns
    assert 'race_id' in columns
    assert 'bib_number' in columns
    assert 'name' in columns
    assert 'age' in columns
    assert 'gender' in columns
    assert 'dossier_complete' in columns
    assert 'checked_in' in columns


def test_finish_times_table_schema(db):
    """Test finish_times table has correct columns."""
    cursor = db.execute("PRAGMA table_info(finish_times)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    assert 'id' in columns
    assert 'race_id' in columns
    assert 'runner_id' in columns
    assert 'bib_number' in columns
    assert 'finish_time' in columns
    assert 'notes' in columns
    assert 'logged_at' in columns


def test_foreign_keys_enabled(db):
    """Test that foreign key constraints are enabled."""
    result = db.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1


def test_bib_number_uniqueness(db, sample_race):
    """Test that bib numbers must be unique across all races."""
    db.execute(
        "INSERT INTO runners (race_id, bib_number, name) VALUES (?, ?, ?)",
        (sample_race['id'], 100, "Test Runner")
    )
    db.commit()
    
    # Try to insert another runner with the same bib number
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO runners (race_id, bib_number, name) VALUES (?, ?, ?)",
            (sample_race['id'], 100, "Another Runner")
        )
        db.commit()


def test_finish_time_uniqueness(db, sample_race, sample_runners):
    """Test that each bib can only have one finish time."""
    bib = sample_runners[0]['bib_number']
    runner_id = sample_runners[0]['id']
    
    db.execute(
        """INSERT INTO finish_times 
           (race_id, runner_id, bib_number, finish_time) 
           VALUES (?, ?, ?, ?)""",
        (sample_race['id'], runner_id, bib, "2026-05-06 09:00:00")
    )
    db.commit()
    
    # Try to insert another finish time for the same bib
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO finish_times 
               (race_id, runner_id, bib_number, finish_time) 
               VALUES (?, ?, ?, ?)""",
            (sample_race['id'], runner_id, bib, "2026-05-06 09:05:00")
        )
        db.commit()


def test_cascade_delete_race(db, sample_race, sample_runners):
    """Test that deleting a race cascades to runners and finish times."""
    # Add a finish time
    runner_id = sample_runners[0]['id']
    bib = sample_runners[0]['bib_number']
    db.execute(
        """INSERT INTO finish_times 
           (race_id, runner_id, bib_number, finish_time) 
           VALUES (?, ?, ?, ?)""",
        (sample_race['id'], runner_id, bib, "2026-05-06 09:00:00")
    )
    db.commit()
    
    # Delete the race
    db.execute("DELETE FROM races WHERE id = ?", (sample_race['id'],))
    db.commit()
    
    # Check that runners and finish times were also deleted
    runners = db.execute(
        "SELECT COUNT(*) FROM runners WHERE race_id = ?", 
        (sample_race['id'],)
    ).fetchone()[0]
    assert runners == 0
    
    finish_times = db.execute(
        "SELECT COUNT(*) FROM finish_times WHERE race_id = ?",
        (sample_race['id'],)
    ).fetchone()[0]
    assert finish_times == 0


def test_schema_migration(temp_db):
    """Test that schema migration drops and recreates tables."""
    # Don't call init_db here since temp_db fixture already did it
    
    conn = sqlite3.connect(temp_db)
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Insert test data
    conn.execute("INSERT INTO races (name) VALUES (?)", ("Old Race",))
    conn.commit()
    
    # Verify data exists
    result = conn.execute("SELECT COUNT(*) FROM races").fetchone()[0]
    assert result == 1
    
    # Change the schema version to trigger migration
    old_version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.execute(f"PRAGMA user_version = {old_version - 1}")
    conn.commit()
    conn.close()
    
    # Re-initialize database (should trigger migration)
    # Need to import fresh to pick up the temp_db path
    import os
    os.environ['DATABASE'] = temp_db
    import sys
    if 'database' in sys.modules:
        del sys.modules['database']
    from database import init_db
    init_db()
    
    # Verify data was cleared
    conn = sqlite3.connect(temp_db)
    result = conn.execute("SELECT COUNT(*) FROM races").fetchone()[0]
    assert result == 0
    conn.close()


def test_default_values(db, sample_race):
    """Test that default values are set correctly."""
    # Insert runner with minimal data
    cursor = db.execute(
        "INSERT INTO runners (race_id, bib_number, name) VALUES (?, ?, ?)",
        (sample_race['id'], 999, "Minimal Runner")
    )
    db.commit()
    
    # Fetch the runner
    runner = db.execute(
        "SELECT * FROM runners WHERE id = ?", 
        (cursor.lastrowid,)
    ).fetchone()
    
    assert runner['dossier_complete'] == 0
    assert runner['checked_in'] == 0
    assert runner['age'] is None
    assert runner['gender'] is None
