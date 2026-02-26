import os
import io
import csv
from datetime import datetime
import sqlite3

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, g, abort)
import openpyxl

from database import init_db, DATABASE

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'race-manager-dev-secret')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

init_db()


# ── DB helpers ──────────────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_race_or_404(race_id):
    race = get_db().execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
    if race is None:
        abort(404)
    return race


# ── Time helpers ────────────────────────────────────────────────────────

def compute_elapsed(finish_time_str, start_time_str):
    """Return 'H:MM:SS' elapsed string, or None if start_time missing / negative."""
    if not finish_time_str or not start_time_str:
        return None
    try:
        ft    = datetime.fromisoformat(finish_time_str.replace(' ', 'T'))
        st    = datetime.fromisoformat(start_time_str.replace(' ', 'T'))
        total = int((ft - st).total_seconds())
        if total < 0:
            return None
        h, rem = divmod(total, 3600)
        m, s   = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"
    except Exception:
        return None


# ── Home ────────────────────────────────────────────────────────────────

def _races_with_stats(db):
    races = db.execute("""
        SELECT r.*, COUNT(ru.id) AS runner_count
        FROM races r
        LEFT JOIN runners ru ON ru.race_id = r.id
        GROUP BY r.id
        ORDER BY (r.start_time IS NULL) ASC, r.start_time ASC
    """).fetchall()
    result = []
    for race in races:
        s = _race_stats(db, race['id'])
        result.append({**dict(race), **s})
    return result


@app.route('/')
def index():
    db    = get_db()
    races = _races_with_stats(db)
    return render_template('index.html', races=races)


@app.route('/races/<int:race_id>/start-time', methods=['POST'])
def set_start_time(race_id):
    get_race_or_404(race_id)
    raw = request.form.get('start_time', '').strip()
    try:
        dt  = datetime.fromisoformat(raw)
        val = dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        flash('Invalid start time.', 'danger')
        return redirect(url_for('index'))
    db = get_db()
    db.execute("UPDATE races SET start_time = ? WHERE id = ?", (val, race_id))
    db.commit()
    flash('Start time saved.', 'success')
    return redirect(url_for('index'))


@app.route('/races/<int:race_id>/delete', methods=['POST'])
def delete_race(race_id):
    race = get_race_or_404(race_id)
    db   = get_db()
    db.execute("DELETE FROM races WHERE id = ?", (race_id,))
    db.commit()
    flash(f'Race "{race["name"]}" deleted.', 'info')
    return redirect(url_for('index'))


# ── Race detail (runner list only) ──────────────────────────────────────

@app.route('/races/<int:race_id>')
def race_detail(race_id):
    race    = get_race_or_404(race_id)
    db      = get_db()
    runners = db.execute("""
        SELECT r.*, ft.finish_time
        FROM runners r
        LEFT JOIN finish_times ft ON ft.runner_id = r.id
        WHERE r.race_id = ?
        ORDER BY r.bib_number ASC
    """, (race_id,)).fetchall()
    return render_template('race.html', race=race, runners=runners)


# ── Import runners ──────────────────────────────────────────────────────

def parse_upload(file_storage):
    filename = file_storage.filename.lower()
    rows     = []

    if filename.endswith('.csv'):
        stream = io.TextIOWrapper(file_storage.stream, encoding='utf-8-sig')
        reader = csv.DictReader(stream)
        for row in reader:
            rows.append({k.strip().lower(): v for k, v in row.items()})

    elif filename.endswith(('.xlsx', '.xls')):
        wb       = openpyxl.load_workbook(file_storage, read_only=True, data_only=True)
        ws       = wb.active
        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            return []
        headers = [str(h).strip().lower() if h is not None else '' for h in all_rows[0]]
        for row in all_rows[1:]:
            rows.append(dict(zip(headers, [str(v) if v is not None else '' for v in row])))

    else:
        raise ValueError("Unsupported file type. Please use .csv or .xlsx")

    return rows


def _do_import(rows, race_id, db, race_lookup=None):
    """
    Insert runners. If race_lookup is given (global import), the 'race' column
    determines the target race; missing races are auto-created.
    Returns (imported, skipped, errors, new_races).
    """
    imported = skipped = errors = new_races = 0

    for row in rows:
        bib_raw = str(row.get('bib_number', '') or '').strip()
        name    = str(row.get('name', '') or '').strip()

        if not bib_raw or not name:
            errors += 1
            continue

        try:
            bib = int(bib_raw)
        except ValueError:
            errors += 1
            continue

        age_raw = str(row.get('age', '') or '').strip()
        try:
            age = int(age_raw) if age_raw and age_raw.lower() != 'n/a' else None
        except ValueError:
            age = None

        gender = str(row.get('gender', '') or '').strip() or None

        target_race_id = race_id
        if race_lookup is not None:
            race_name_raw  = str(row.get('race', '') or '').strip()
            target_race_id = race_lookup.get(race_name_raw.lower())
            if target_race_id is None:
                if race_name_raw:
                    # Auto-create the race (start_time set later by the user)
                    cur = db.execute(
                        "INSERT INTO races (name) VALUES (?)", (race_name_raw,)
                    )
                    target_race_id = cur.lastrowid
                    race_lookup[race_name_raw.lower()] = target_race_id
                    new_races += 1
                else:
                    errors += 1
                    continue

        existing = db.execute(
            "SELECT id, race_id FROM runners WHERE bib_number = ?", (bib,)
        ).fetchone()

        if existing:
            skipped += 1 if existing['race_id'] == target_race_id else 0
            if existing['race_id'] != target_race_id:
                errors += 1
            continue

        db.execute(
            "INSERT INTO runners (race_id, bib_number, name, age, gender) VALUES (?, ?, ?, ?, ?)",
            (target_race_id, bib, name, age, gender)
        )
        imported += 1

    db.commit()
    return imported, skipped, errors, new_races


def _import_flash(imported, skipped, errors, new_races=0):
    parts = [f'Imported {imported} runner{"s" if imported != 1 else ""}.']
    if new_races:
        parts.append(f'{new_races} race{"s" if new_races != 1 else ""} created automatically — set their start times below.')
    if skipped:
        parts.append(f'{skipped} skipped (already imported).')
    if errors:
        parts.append(f'{errors} skipped (errors or bib already in another race).')
    return ' '.join(parts), 'success' if imported > 0 else 'warning'


@app.route('/import', methods=['POST'])
def import_runners_global():
    if 'file' not in request.files or request.files['file'].filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('index'))

    file = request.files['file']
    try:
        rows = parse_upload(file)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('index'))

    if not rows:
        flash('The file contains no data rows.', 'danger')
        return redirect(url_for('index'))

    missing = {'bib_number', 'name', 'race'} - set(rows[0].keys())
    if missing:
        flash(f'Missing required columns: {", ".join(sorted(missing))}', 'danger')
        return redirect(url_for('index'))

    db = get_db()
    race_lookup = {r['name'].lower(): r['id']
                   for r in db.execute("SELECT id, name FROM races").fetchall()}

    imported, skipped, errors, new_races = _do_import(rows, None, db, race_lookup=race_lookup)
    msg, cat = _import_flash(imported, skipped, errors, new_races)
    flash(msg, cat)
    return redirect(url_for('index'))


# ── Check-in ────────────────────────────────────────────────────────────

@app.route('/checkin')
def checkin():
    db    = get_db()
    races = db.execute("""
        SELECT * FROM races
        ORDER BY (start_time IS NULL) ASC, start_time ASC
    """).fetchall()

    groups = []
    total_runners = total_checked = 0

    for race in races:
        runners = db.execute("""
            SELECT r.*, ft.finish_time
            FROM runners r
            LEFT JOIN finish_times ft ON ft.runner_id = r.id
            WHERE r.race_id = ?
            ORDER BY r.bib_number ASC
        """, (race['id'],)).fetchall()

        checked = sum(1 for r in runners if r['checked_in'])
        total_runners += len(runners)
        total_checked += checked

        groups.append({
            'race':     dict(race),
            'runners':  [dict(r) for r in runners],
            'checked':  checked,
            'total':    len(runners),
        })

    return render_template('checkin.html',
        groups=groups,
        total_runners=total_runners,
        total_checked=total_checked,
    )


@app.route('/races/<int:race_id>/runners/<int:runner_id>/checkin', methods=['POST'])
def toggle_checkin(race_id, runner_id):
    get_race_or_404(race_id)
    data       = request.get_json(silent=True) or {}
    checked_in = 1 if data.get('checked_in') else 0

    db = get_db()
    db.execute(
        "UPDATE runners SET checked_in = ? WHERE id = ? AND race_id = ?",
        (checked_in, runner_id, race_id)
    )
    db.commit()

    race_checked = db.execute(
        "SELECT COUNT(*) FROM runners WHERE race_id = ? AND checked_in = 1", (race_id,)
    ).fetchone()[0]
    race_total = db.execute(
        "SELECT COUNT(*) FROM runners WHERE race_id = ?", (race_id,)
    ).fetchone()[0]
    global_checked = db.execute(
        "SELECT COUNT(*) FROM runners WHERE checked_in = 1"
    ).fetchone()[0]
    global_total = db.execute(
        "SELECT COUNT(*) FROM runners"
    ).fetchone()[0]

    return jsonify(ok=True, checked_in=checked_in,
                   race_checked=race_checked, race_total=race_total,
                   global_checked=global_checked, global_total=global_total)


@app.route('/races/<int:race_id>/runners/checkin-all', methods=['POST'])
def checkin_all(race_id):
    get_race_or_404(race_id)
    db = get_db()
    db.execute("UPDATE runners SET checked_in = 1 WHERE race_id = ?", (race_id,))
    db.commit()

    race_total = db.execute(
        "SELECT COUNT(*) FROM runners WHERE race_id = ?", (race_id,)
    ).fetchone()[0]
    global_checked = db.execute(
        "SELECT COUNT(*) FROM runners WHERE checked_in = 1"
    ).fetchone()[0]
    global_total = db.execute("SELECT COUNT(*) FROM runners").fetchone()[0]

    return jsonify(ok=True, race_checked=race_total, race_total=race_total,
                   global_checked=global_checked, global_total=global_total)


@app.route('/checkin/all', methods=['POST'])
def checkin_all_global():
    db = get_db()
    db.execute("UPDATE runners SET checked_in = 1")
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM runners").fetchone()[0]
    return jsonify(ok=True, global_checked=total, global_total=total)


# ── Finish Line (global) ────────────────────────────────────────────────

def _race_stats(db, race_id):
    total_checked_in = db.execute(
        "SELECT COUNT(*) FROM runners WHERE race_id = ? AND checked_in = 1", (race_id,)
    ).fetchone()[0]
    finished = db.execute(
        """SELECT COUNT(*) FROM finish_times ft
           JOIN runners r ON r.id = ft.runner_id
           WHERE ft.race_id = ? AND r.checked_in = 1""",
        (race_id,)
    ).fetchone()[0]
    return {'finished': finished,
            'still_running': max(0, total_checked_in - finished),
            'total': total_checked_in}


@app.route('/finish-line')
def finish_line():
    db     = get_db()
    races  = db.execute(
        "SELECT * FROM races ORDER BY (start_time IS NULL) ASC, start_time ASC"
    ).fetchall()

    recent = db.execute("""
        SELECT ft.*, r.name AS runner_name, r.race_id,
               ra.name AS race_name, ra.start_time AS race_start_time
        FROM finish_times ft
        LEFT JOIN runners r  ON r.id  = ft.runner_id
        LEFT JOIN races   ra ON ra.id = ft.race_id
        ORDER BY ft.finish_time DESC
        LIMIT 200
    """).fetchall()

    race_stats = []
    for race in races:
        s = _race_stats(db, race['id'])
        race_stats.append({**dict(race), **s})

    recent_list = []
    for ft in recent:
        entry          = dict(ft)
        entry['elapsed'] = compute_elapsed(ft['finish_time'], ft['race_start_time'])
        recent_list.append(entry)

    return render_template('finish_line.html', races=race_stats, recent=recent_list)


@app.route('/finish-line/stats')
def finish_line_stats():
    db    = get_db()
    races = db.execute(
        "SELECT * FROM races ORDER BY (start_time IS NULL) ASC, start_time ASC"
    ).fetchall()
    return jsonify([{
        'id':          race['id'],
        'name':        race['name'],
        'start_time':  race['start_time'],
        **_race_stats(db, race['id'])
    } for race in races])


@app.route('/finish-line/log', methods=['POST'])
def log_finish_global():
    data            = request.get_json(silent=True) or {}
    bib_raw         = data.get('bib_number')
    finish_time_raw = str(data.get('finish_time', '') or '').strip()

    if not bib_raw:
        return jsonify(error='Bib number is required.'), 400
    try:
        bib = int(bib_raw)
    except (ValueError, TypeError):
        return jsonify(error='Bib number must be an integer.'), 400
    try:
        datetime.fromisoformat(finish_time_raw)
    except (ValueError, TypeError):
        return jsonify(error='Invalid finish time.'), 400

    db     = get_db()
    runner = db.execute("SELECT * FROM runners WHERE bib_number = ?", (bib,)).fetchone()
    if not runner:
        return jsonify(error=f'Bib {bib} not found in any race.', code='not_found'), 404

    race_id = runner['race_id']
    race    = db.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()

    if db.execute("SELECT id FROM finish_times WHERE bib_number = ?", (bib,)).fetchone():
        return jsonify(
            error=f'Bib {bib} ({runner["name"]}) already has a finish time logged.',
            code='duplicate'
        ), 409

    cur = db.execute(
        "INSERT INTO finish_times (race_id, runner_id, bib_number, finish_time) VALUES (?, ?, ?, ?)",
        (race_id, runner['id'], bib, finish_time_raw)
    )
    db.commit()

    elapsed = compute_elapsed(finish_time_raw, race['start_time'])
    stats   = _race_stats(db, race_id)

    return jsonify(ok=True, finish={
        'id':          cur.lastrowid,
        'bib_number':  bib,
        'finish_time': finish_time_raw,
        'runner_name': runner['name'],
        'race_id':     race_id,
        'race_name':   race['name'],
        'elapsed':     elapsed,
    }, race_stats={**stats, 'id': race_id})


# ── Finish times — global edit / delete ────────────────────────────────

@app.route('/finish/<int:finish_id>', methods=['PUT'])
def edit_finish_global(finish_id):
    data            = request.get_json(silent=True) or {}
    finish_time_raw = str(data.get('finish_time', '') or '').strip()
    notes           = str(data.get('notes', '') or '').strip() or None

    try:
        datetime.fromisoformat(finish_time_raw)
    except (ValueError, TypeError):
        return jsonify(error='Invalid finish time.'), 400

    db  = get_db()
    row = db.execute("SELECT race_id FROM finish_times WHERE id = ?", (finish_id,)).fetchone()
    if not row:
        abort(404)

    db.execute(
        "UPDATE finish_times SET finish_time = ?, notes = ? WHERE id = ?",
        (finish_time_raw, notes, finish_id)
    )
    db.commit()

    race    = db.execute("SELECT * FROM races WHERE id = ?", (row['race_id'],)).fetchone()
    elapsed = compute_elapsed(finish_time_raw, race['start_time']) if race else None

    return jsonify(ok=True, finish_time=finish_time_raw, notes=notes, elapsed=elapsed)


@app.route('/finish/<int:finish_id>', methods=['DELETE'])
def delete_finish_global(finish_id):
    db  = get_db()
    row = db.execute("SELECT race_id FROM finish_times WHERE id = ?", (finish_id,)).fetchone()
    if not row:
        abort(404)
    race_id = row['race_id']
    db.execute("DELETE FROM finish_times WHERE id = ?", (finish_id,))
    db.commit()
    return jsonify(ok=True, race_stats={**_race_stats(db, race_id), 'id': race_id})


# ── Ranking ─────────────────────────────────────────────────────────────

def compute_ranking(race_id, start_time):
    db   = get_db()
    rows = db.execute("""
        SELECT r.id, r.bib_number, r.name, r.age, r.gender, r.checked_in,
               ft.finish_time, ft.notes, ft.id AS finish_id
        FROM runners r
        LEFT JOIN finish_times ft ON ft.runner_id = r.id
        WHERE r.race_id = ?
        ORDER BY ft.finish_time ASC, r.bib_number ASC
    """, (race_id,)).fetchall()

    finishers, still_running, dns = [], [], []
    rank = 1

    for row in rows:
        entry = dict(row)
        if entry['finish_time']:
            entry['rank']    = rank
            entry['elapsed'] = compute_elapsed(entry['finish_time'], start_time)
            rank += 1
            finishers.append(entry)
        elif entry['checked_in']:
            entry['rank'] = entry['elapsed'] = None
            still_running.append(entry)
        else:
            entry['rank'] = entry['elapsed'] = None
            dns.append(entry)

    return {
        'finishers':     finishers,
        'still_running': still_running,
        'dns':           dns,
        'counts': {
            'finished':         len(finishers),
            'still_running':    len(still_running),
            'dns':              len(dns),
            'total_checked_in': len(finishers) + len(still_running),
        }
    }


@app.route('/races/<int:race_id>/ranking')
def ranking_api(race_id):
    race = get_race_or_404(race_id)
    return jsonify(compute_ranking(race_id, race['start_time']))


@app.route('/ranking')
def ranking_page():
    db    = get_db()
    races = db.execute(
        "SELECT * FROM races ORDER BY (start_time IS NULL) ASC, start_time ASC"
    ).fetchall()
    return render_template('ranking.html', races=[dict(r) for r in races])


# ── Health check ────────────────────────────────────────────────────────

@app.route('/health')
def health():
    try:
        get_db().execute("SELECT 1").fetchone()
        return jsonify(status='ok'), 200
    except Exception as e:
        return jsonify(status='error', detail=str(e)), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
