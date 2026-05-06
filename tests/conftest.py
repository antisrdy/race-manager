"""Pytest configuration and shared fixtures."""
import os
import tempfile
import pytest
import sqlite3


@pytest.fixture(scope='function')
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Set the database path for the test
    original_db = os.environ.get('DATABASE')
    os.environ['DATABASE'] = path
    
    # Force reload of database module to pick up new DATABASE path
    import sys
    if 'database' in sys.modules:
        del sys.modules['database']
    if 'app' in sys.modules:
        del sys.modules['app']
    
    # Now import and initialize
    import database
    database.init_db()
    
    yield path
    
    # Cleanup
    try:
        if os.path.exists(path):
            os.unlink(path)
    except:
        pass
    
    # Restore original database setting
    if original_db:
        os.environ['DATABASE'] = original_db
    elif 'DATABASE' in os.environ:
        del os.environ['DATABASE']
    
    # Clean up modules to ensure fresh imports next time
    if 'database' in sys.modules:
        del sys.modules['database']
    if 'app' in sys.modules:
        del sys.modules['app']


@pytest.fixture
def db(temp_db):
    """Return a database connection to the test database."""
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


@pytest.fixture
def app(temp_db):
    """Create and configure a test Flask application."""
    # Import app after database is set up
    from app import app as flask_app
    
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
    })
    
    # Clear any cached db connections
    with flask_app.app_context():
        # Force close any existing connections
        from flask import g
        if hasattr(g, 'db'):
            delattr(g, 'db')
    
    yield flask_app


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def sample_race(db):
    """Create a sample race in the database."""
    cursor = db.execute(
        "INSERT INTO races (name, start_time) VALUES (?, ?)",
        ("Test Race 10K", "2026-05-06 08:00:00")
    )
    db.commit()
    race_id = cursor.lastrowid
    return {
        'id': race_id,
        'name': "Test Race 10K",
        'start_time': "2026-05-06 08:00:00"
    }


@pytest.fixture
def sample_runners(db, sample_race):
    """Create sample runners in the database."""
    runners = [
        (sample_race['id'], 1, "John Doe", 30, "M", 1, 1),
        (sample_race['id'], 2, "Jane Smith", 25, "F", 1, 1),
        (sample_race['id'], 3, "Bob Johnson", 35, "M", 0, 0),
        (sample_race['id'], 4, "Alice Williams", 28, "F", 1, 0),
    ]
    
    for runner in runners:
        db.execute(
            """INSERT INTO runners 
               (race_id, bib_number, name, age, gender, dossier_complete, checked_in) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            runner
        )
    db.commit()
    
    return [
        {'id': i+1, 'race_id': r[0], 'bib_number': r[1], 'name': r[2], 
         'age': r[3], 'gender': r[4], 'dossier_complete': r[5], 'checked_in': r[6]}
        for i, r in enumerate(runners)
    ]
