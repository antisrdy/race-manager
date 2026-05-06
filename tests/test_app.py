"""Integration tests for the Flask application."""
import json
import io
import csv
from datetime import datetime
import pytest


class TestHealthCheck:
    """Tests for the health check endpoint."""
    
    def test_health_endpoint(self, client):
        """Test the health check endpoint returns ok."""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestHomePage:
    """Tests for the home page."""
    
    def test_index_page_loads(self, client):
        """Test that the index page loads successfully."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Race Manager' in response.data or b'race' in response.data.lower()
    
    def test_index_shows_races(self, client, sample_race, sample_runners):
        """Test that the index page shows races."""
        response = client.get('/')
        assert response.status_code == 200
        assert sample_race['name'].encode() in response.data


class TestRaceManagement:
    """Tests for race management endpoints."""
    
    def test_set_start_time(self, client, sample_race):
        """Test setting a race start time."""
        response = client.post(
            f'/races/{sample_race["id"]}/start-time',
            data={'start_time': '2026-05-10T10:00:00'}
        )
        assert response.status_code == 302  # Redirect
    
    def test_set_invalid_start_time(self, client, sample_race):
        """Test setting an invalid start time."""
        response = client.post(
            f'/races/{sample_race["id"]}/start-time',
            data={'start_time': 'invalid-date'},
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Heure de d' in response.data
    
    def test_delete_race(self, client, sample_race):
        """Test deleting a race."""
        response = client.post(
            f'/races/{sample_race["id"]}/delete',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'supprim' in response.data.lower()
    
    def test_race_detail_page(self, client, sample_race, sample_runners):
        """Test the race detail page."""
        response = client.get(f'/races/{sample_race["id"]}')
        assert response.status_code == 200
        assert sample_race['name'].encode() in response.data
        # Check that runners are displayed
        assert sample_runners[0]['name'].encode() in response.data
    
    def test_race_not_found(self, client):
        """Test accessing a non-existent race."""
        response = client.get('/races/99999')
        assert response.status_code == 404


class TestRunnerImport:
    """Tests for runner import functionality."""
    
    def test_import_csv_english(self, client, sample_race):
        """Test importing runners from a CSV file with English headers."""
        csv_data = io.StringIO()
        writer = csv.DictWriter(
            csv_data, 
            fieldnames=['bib_number', 'name', 'age', 'gender', 'race', 'dossier_complete']
        )
        writer.writeheader()
        writer.writerow({
            'bib_number': '10',
            'name': 'Test Runner',
            'age': '30',
            'gender': 'M',
            'race': sample_race['name'],
            'dossier_complete': '1'
        })
        
        csv_data.seek(0)
        data = {
            'file': (io.BytesIO(csv_data.getvalue().encode()), 'runners.csv')
        }
        
        response = client.post(
            '/import',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'1 coureur import' in response.data
    
    def test_import_csv_french(self, client, sample_race):
        """Test importing runners from a CSV file with French headers."""
        csv_data = io.StringIO()
        writer = csv.DictWriter(
            csv_data,
            fieldnames=['DOSSARD', 'NOM', 'PRENOM', 'SEXE', 'DISTANCE', 'DOSSIER']
        )
        writer.writeheader()
        writer.writerow({
            'DOSSARD': '20',
            'NOM': 'Dupont',
            'PRENOM': 'Jean',
            'SEXE': 'M',
            'DISTANCE': sample_race['name'],
            'DOSSIER': 'COMPLET'
        })
        
        csv_data.seek(0)
        data = {
            'file': (io.BytesIO(csv_data.getvalue().encode()), 'runners.csv')
        }
        
        response = client.post(
            '/import',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'1 coureur import' in response.data
    
    def test_import_no_file(self, client):
        """Test import with no file selected."""
        response = client.post(
            '/import',
            data={},
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Aucun fichier' in response.data
    
    def test_import_missing_columns(self, client):
        """Test import with missing required columns."""
        csv_data = io.StringIO()
        writer = csv.DictWriter(csv_data, fieldnames=['bib_number', 'name'])
        writer.writeheader()
        writer.writerow({'bib_number': '30', 'name': 'Test'})
        
        csv_data.seek(0)
        data = {
            'file': (io.BytesIO(csv_data.getvalue().encode()), 'runners.csv')
        }
        
        response = client.post(
            '/import',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Colonnes obligatoires manquantes' in response.data
    
    def test_import_missing_dossier_complete(self, client):
        """Test import with missing dossier_complete column."""
        csv_data = io.StringIO()
        writer = csv.DictWriter(csv_data, fieldnames=['bib_number', 'name', 'race'])
        writer.writeheader()
        writer.writerow({'bib_number': '40', 'name': 'Test Runner', 'race': 'Test Race'})
        
        csv_data.seek(0)
        data = {
            'file': (io.BytesIO(csv_data.getvalue().encode()), 'runners.csv')
        }
        
        response = client.post(
            '/import',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'Colonnes obligatoires manquantes' in response.data
        assert b'dossier_complete' in response.data
    
    def test_import_creates_new_race(self, client):
        """Test that import automatically creates races if they don't exist."""
        csv_data = io.StringIO()
        writer = csv.DictWriter(
            csv_data,
            fieldnames=['bib_number', 'name', 'race', 'dossier_complete']
        )
        writer.writeheader()
        writer.writerow({
            'bib_number': '50',
            'name': 'Runner One',
            'race': 'New Race 5K',
            'dossier_complete': '1'
        })
        
        csv_data.seek(0)
        data = {
            'file': (io.BytesIO(csv_data.getvalue().encode()), 'runners.csv')
        }
        
        response = client.post(
            '/import',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'1 course' in response.data
        assert b'automatiquement' in response.data
    
    def test_import_duplicate_bib(self, client, sample_race, sample_runners):
        """Test that duplicate bib numbers are skipped."""
        existing_bib = sample_runners[0]['bib_number']
        
        csv_data = io.StringIO()
        writer = csv.DictWriter(
            csv_data,
            fieldnames=['bib_number', 'name', 'race', 'dossier_complete']
        )
        writer.writeheader()
        writer.writerow({
            'bib_number': str(existing_bib),
            'name': 'Duplicate Runner',
            'race': sample_race['name'],
            'dossier_complete': '1'
        })
        
        csv_data.seek(0)
        data = {
            'file': (io.BytesIO(csv_data.getvalue().encode()), 'runners.csv')
        }
        
        response = client.post(
            '/import',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'ignor' in response.data


class TestCheckIn:
    """Tests for check-in functionality."""
    
    def test_checkin_page_loads(self, client):
        """Test that the check-in page loads."""
        response = client.get('/checkin')
        assert response.status_code == 200
    
    def test_checkin_shows_runners(self, client, sample_race, sample_runners):
        """Test that check-in page shows runners."""
        response = client.get('/checkin')
        assert response.status_code == 200
        assert sample_runners[0]['name'].encode() in response.data
    
    def test_toggle_checkin(self, client, sample_race, sample_runners):
        """Test toggling check-in status for a runner."""
        runner = sample_runners[2]  # Not checked in initially
        response = client.post(
            f'/races/{sample_race["id"]}/runners/{runner["id"]}/checkin',
            json={'checked_in': True}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['checked_in'] == 1
    
    def test_checkin_all_race(self, client, sample_race):
        """Test checking in all runners for a race."""
        response = client.post(f'/races/{sample_race["id"]}/runners/checkin-all')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['race_checked'] == data['race_total']
    
    def test_checkin_all_global(self, client, sample_runners):
        """Test checking in all runners globally."""
        response = client.post('/checkin/all')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['global_checked'] == data['global_total']


class TestFinishLine:
    """Tests for finish line functionality."""
    
    def test_finish_line_page_loads(self, client):
        """Test that the finish line page loads."""
        response = client.get('/finish-line')
        assert response.status_code == 200
    
    def test_finish_line_stats(self, client, sample_race):
        """Test the finish line stats endpoint."""
        response = client.get('/finish-line/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[0]['id'] == sample_race['id']
    
    def test_log_finish_time(self, client, sample_race, sample_runners):
        """Test logging a finish time."""
        runner = sample_runners[0]
        response = client.post(
            '/finish-line/log',
            json={
                'bib_number': runner['bib_number'],
                'finish_time': '2026-05-06 09:30:00'
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['finish']['bib_number'] == runner['bib_number']
    
    def test_log_finish_time_invalid_bib(self, client):
        """Test logging finish time with invalid bib number."""
        response = client.post(
            '/finish-line/log',
            json={
                'bib_number': 'invalid',
                'finish_time': '2026-05-06 09:30:00'
            }
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_log_finish_time_nonexistent_bib(self, client):
        """Test logging finish time for non-existent bib."""
        response = client.post(
            '/finish-line/log',
            json={
                'bib_number': 99999,
                'finish_time': '2026-05-06 09:30:00'
            }
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['code'] == 'not_found'
    
    def test_log_finish_time_duplicate(self, client, sample_race, sample_runners):
        """Test logging duplicate finish time."""
        runner = sample_runners[0]
        
        # Log first time
        client.post(
            '/finish-line/log',
            json={
                'bib_number': runner['bib_number'],
                'finish_time': '2026-05-06 09:30:00'
            }
        )
        
        # Try to log again
        response = client.post(
            '/finish-line/log',
            json={
                'bib_number': runner['bib_number'],
                'finish_time': '2026-05-06 09:35:00'
            }
        )
        assert response.status_code == 409
        data = json.loads(response.data)
        assert data['code'] == 'duplicate'
    
    def test_edit_finish_time(self, client, sample_race, sample_runners, db):
        """Test editing a finish time."""
        runner = sample_runners[0]
        
        # Create a finish time
        cursor = db.execute(
            """INSERT INTO finish_times 
               (race_id, runner_id, bib_number, finish_time) 
               VALUES (?, ?, ?, ?)""",
            (sample_race['id'], runner['id'], runner['bib_number'], 
             '2026-05-06 09:30:00')
        )
        db.commit()
        finish_id = cursor.lastrowid
        
        # Edit it
        response = client.put(
            f'/finish/{finish_id}',
            json={
                'finish_time': '2026-05-06 09:35:00',
                'notes': 'Corrected time'
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['finish_time'] == '2026-05-06 09:35:00'
        assert data['notes'] == 'Corrected time'
    
    def test_delete_finish_time(self, client, sample_race, sample_runners, db):
        """Test deleting a finish time."""
        runner = sample_runners[0]
        
        # Create a finish time
        cursor = db.execute(
            """INSERT INTO finish_times 
               (race_id, runner_id, bib_number, finish_time) 
               VALUES (?, ?, ?, ?)""",
            (sample_race['id'], runner['id'], runner['bib_number'],
             '2026-05-06 09:30:00')
        )
        db.commit()
        finish_id = cursor.lastrowid
        
        # Delete it
        response = client.delete(f'/finish/{finish_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True


class TestRanking:
    """Tests for ranking functionality."""
    
    def test_ranking_page_loads(self, client):
        """Test that the ranking page loads."""
        response = client.get('/ranking')
        assert response.status_code == 200
    
    def test_ranking_api(self, client, sample_race, sample_runners, db):
        """Test the ranking API endpoint."""
        # Add finish times for some runners
        db.execute(
            """INSERT INTO finish_times 
               (race_id, runner_id, bib_number, finish_time) 
               VALUES (?, ?, ?, ?)""",
            (sample_race['id'], sample_runners[0]['id'], 
             sample_runners[0]['bib_number'], '2026-05-06 09:30:00')
        )
        db.execute(
            """INSERT INTO finish_times 
               (race_id, runner_id, bib_number, finish_time) 
               VALUES (?, ?, ?, ?)""",
            (sample_race['id'], sample_runners[1]['id'],
             sample_runners[1]['bib_number'], '2026-05-06 09:25:00')
        )
        db.commit()
        
        response = client.get(f'/races/{sample_race["id"]}/ranking')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check structure
        assert 'finishers' in data
        assert 'still_running' in data
        assert 'dns' in data
        assert 'counts' in data
        
        # Check ranking order (fastest first)
        assert len(data['finishers']) == 2
        assert data['finishers'][0]['rank'] == 1
        assert data['finishers'][0]['bib_number'] == sample_runners[1]['bib_number']
        assert data['finishers'][1]['rank'] == 2
        assert data['finishers'][1]['bib_number'] == sample_runners[0]['bib_number']
        
        # Check counts
        assert data['counts']['finished'] == 2
        assert data['counts']['still_running'] == 0


class TestDatabaseConnection:
    """Tests for database connection management."""
    
    def test_db_connection_in_request_context(self, app):
        """Test that database connection is available in request context."""
        with app.test_request_context():
            from app import get_db
            db = get_db()
            assert db is not None
            result = db.execute("SELECT 1").fetchone()
            assert result[0] == 1
    
    def test_db_connection_closed_after_request(self, app):
        """Test that database connection is closed after request."""
        with app.test_request_context():
            from app import get_db, close_db
            db = get_db()
            assert db is not None
            close_db()
            # After closing, g should not have db
            from flask import g
            assert 'db' not in g
