from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class FileAccess(db.Model):
    __tablename__ = 'file_access'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    server = db.Column(db.String(255), index=True)
    username = db.Column(db.String(255), index=True)
    file_path = db.Column(db.String(1024))
    share_name = db.Column(db.String(255))
    action = db.Column(db.String(50))  # 'opened' or 'closed'
    file_id = db.Column(db.String(255))


class ServerConfig(db.Model):
    __tablename__ = 'server_config'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    hostname = db.Column(db.String(255))  # None/empty = local
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
