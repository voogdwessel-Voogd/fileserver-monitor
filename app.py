from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta

from config import Config
from db import db, FileAccess, ServerConfig
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

    entries = query.order_by(FileAccess.timestamp.desc()).paginate(
        page=page, per_page=50
    )
    users = db.session.query(FileAccess.username).distinct().all()

    return render_template(
        'index.html',
        entries=entries,
        users=[u[0] for u in users],
        filters={
            'user': user_filter,
            'action': action_filter,
            'hours': hours,
        },
    )


@app.route('/live')
def live():
    return render_template('live.html')


@app.route('/api/live')
def api_live():
    return jsonify(monitor.get_recent_events())


@app.route('/servers')
def servers():
    all_servers = ServerConfig.query.all()
    return render_template('servers.html', servers=all_servers)


@app.route('/servers/add', methods=['POST'])
def add_server():
    name = request.form.get('name', '').strip()
    hostname = request.form.get('hostname', '').strip()

    if not name:
        flash('Server naam is verplicht', 'error')
        return redirect(url_for('servers'))

    server = ServerConfig(name=name, hostname=hostname or None)
    db.session.add(server)
    db.session.commit()
    flash(f'Server "{name}" toegevoegd', 'success')
    return redirect(url_for('servers'))


@app.route('/servers/<int:server_id>/toggle', methods=['POST'])
def toggle_server(server_id):
    server = db.get_or_404(ServerConfig, server_id)
    server.is_active = not server.is_active
    db.session.commit()
    return redirect(url_for('servers'))


@app.route('/servers/<int:server_id>/delete', methods=['POST'])
def delete_server(server_id):
    server = db.get_or_404(ServerConfig, server_id)
    name = server.name
    db.session.delete(server)
    db.session.commit()
    flash(f'Server "{name}" verwijderd', 'success')
    return redirect(url_for('servers'))


with app.app_context():
    db.create_all()
    if ServerConfig.query.count() == 0:
        db.session.add(ServerConfig(name='Lokaal', hostname=''))
        db.session.commit()

monitor.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
