from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta

from config import Config
from db import db, FileAccess, ServerConfig
from monitor import SmbMonitor

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
monitor = SmbMonitor(app, db)


@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    server_filter = request.args.get('server', '')
    user_filter = request.args.get('user', '')
    action_filter = request.args.get('action', '')
    hours = request.args.get('hours', 24, type=int)

    query = FileAccess.query
    since = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(FileAccess.timestamp >= since)

    if server_filter:
        query = query.filter(FileAccess.server == server_filter)
    if user_filter:
        query = query.filter(FileAccess.username.ilike(f'%{user_filter}%'))
    if action_filter:
        query = query.filter(FileAccess.action == action_filter)

    entries = query.order_by(FileAccess.timestamp.desc()).paginate(
        page=page, per_page=50
    )
    servers = ServerConfig.query.filter_by(is_active=True).all()
    users = db.session.query(FileAccess.username).distinct().all()

    return render_template(
        'index.html',
        entries=entries,
        servers=servers,
        users=[u[0] for u in users],
        filters={
            'server': server_filter,
            'user': user_filter,
            'action': action_filter,
            'hours': hours,
        },
    )


@app.route('/live')
def live():
    servers = ServerConfig.query.filter_by(is_active=True).all()
    return render_template('live.html', servers=servers)


@app.route('/api/live')
def api_live():
    server_key = request.args.get('server', 'local')
    files = monitor.get_current_open(server_key)
    return jsonify(files)


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
