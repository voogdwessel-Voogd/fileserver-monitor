from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta

from config import Config
from db import db, FileAccess, ServerConfig, AccountFilter, WatchPath, AppSetting, get_setting
from monitor import EventLogMonitor

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
monitor = EventLogMonitor(app, db)


@app.template_filter('basename')
def basename_filter(path):
    if not path:
        return '-'
    return path.replace('/', '\\').split('\\')[-1]


@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    user_filter = request.args.get('user', '')
    action_filter = request.args.get('action', '')
    hours = request.args.get('hours', 24, type=int)

    query = FileAccess.query
    since = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(FileAccess.timestamp >= since)

    if user_filter:
        query = query.filter(FileAccess.username.ilike(f'%{user_filter}%'))
    if action_filter:
        query = query.filter(FileAccess.action == action_filter)

    entries = query.order_by(FileAccess.timestamp.desc()).paginate(page=page, per_page=50)
    users = db.session.query(FileAccess.username).distinct().all()

    return render_template(
        'index.html',
        entries=entries,
        users=[u[0] for u in users],
        filters={'user': user_filter, 'action': action_filter, 'hours': hours},
    )


@app.route('/live')
def live():
    return render_template('live.html')


@app.route('/api/live')
def api_live():
    return jsonify(monitor.get_recent_events())


# ── Instellingen ──────────────────────────────────────────────────────────────

@app.route('/settings')
def settings_page():
    return render_template('settings.html',
        settings={
            'POLL_INTERVAL': get_setting('POLL_INTERVAL', Config.POLL_INTERVAL),
            'RETENTION_DAYS': get_setting('RETENTION_DAYS', Config.RETENTION_DAYS),
        },
        account_filters=AccountFilter.query.all(),
        watch_paths=WatchPath.query.all(),
        servers=ServerConfig.query.all(),
    )


@app.route('/settings/update', methods=['POST'])
def update_settings():
    errors = []
    for key, label, min_val in [
        ('POLL_INTERVAL', 'Poll interval', 5),
        ('RETENTION_DAYS', 'Bewaarperiode', 0),
    ]:
        raw = request.form.get(key, '').strip()
        if not raw:
            continue
        if not raw.isdigit() or int(raw) < min_val:
            errors.append(f'{label} moet een geheel getal zijn van minimaal {min_val}.')
            continue
        s = db.session.get(AppSetting, key)
        if s:
            s.value = raw
        else:
            db.session.add(AppSetting(key=key, value=raw))
    if errors:
        for e in errors:
            flash(e, 'error')
    else:
        db.session.commit()
        flash('Instellingen opgeslagen', 'success')
    return redirect(url_for('settings_page'))


# Mappen

@app.route('/paths/add', methods=['POST'])
def add_path():
    path = request.form.get('path', '').strip()
    if not path:
        flash('Pad is verplicht', 'error')
    else:
        db.session.add(WatchPath(path=path))
        db.session.commit()
        flash(f'Map "{path}" toegevoegd', 'success')
    return redirect(url_for('settings_page'))


@app.route('/paths/<int:path_id>/toggle', methods=['POST'])
def toggle_path(path_id):
    p = db.get_or_404(WatchPath, path_id)
    p.is_active = not p.is_active
    db.session.commit()
    return redirect(url_for('settings_page'))


@app.route('/paths/<int:path_id>/delete', methods=['POST'])
def delete_path(path_id):
    p = db.get_or_404(WatchPath, path_id)
    db.session.delete(p)
    db.session.commit()
    flash(f'Map "{p.path}" verwijderd', 'success')
    return redirect(url_for('settings_page'))


# Accounts

@app.route('/accounts/add', methods=['POST'])
def add_account_filter():
    pattern = request.form.get('pattern', '').strip()
    if not pattern:
        flash('Patroon is verplicht', 'error')
    else:
        db.session.add(AccountFilter(pattern=pattern))
        db.session.commit()
        flash(f'Patroon "{pattern}" toegevoegd', 'success')
    return redirect(url_for('settings_page'))


@app.route('/accounts/<int:filter_id>/toggle', methods=['POST'])
def toggle_account_filter(filter_id):
    f = db.get_or_404(AccountFilter, filter_id)
    f.is_active = not f.is_active
    db.session.commit()
    return redirect(url_for('settings_page'))


@app.route('/accounts/<int:filter_id>/delete', methods=['POST'])
def delete_account_filter(filter_id):
    f = db.get_or_404(AccountFilter, filter_id)
    db.session.delete(f)
    db.session.commit()
    flash(f'Patroon "{f.pattern}" verwijderd', 'success')
    return redirect(url_for('settings_page'))


# Servers

@app.route('/servers/add', methods=['POST'])
def add_server():
    name = request.form.get('name', '').strip()
    hostname = request.form.get('hostname', '').strip()
    if not name:
        flash('Server naam is verplicht', 'error')
    else:
        db.session.add(ServerConfig(name=name, hostname=hostname or None))
        db.session.commit()
        flash(f'Server "{name}" toegevoegd', 'success')
    return redirect(url_for('settings_page'))


@app.route('/servers/<int:server_id>/toggle', methods=['POST'])
def toggle_server(server_id):
    server = db.get_or_404(ServerConfig, server_id)
    server.is_active = not server.is_active
    db.session.commit()
    return redirect(url_for('settings_page'))


@app.route('/servers/<int:server_id>/delete', methods=['POST'])
def delete_server(server_id):
    server = db.get_or_404(ServerConfig, server_id)
    db.session.delete(server)
    db.session.commit()
    flash(f'Server "{server.name}" verwijderd', 'success')
    return redirect(url_for('settings_page'))


with app.app_context():
    db.create_all()
    if ServerConfig.query.count() == 0:
        db.session.add(ServerConfig(name='Lokaal', hostname=''))
        db.session.commit()

monitor.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
