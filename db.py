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
    process_name = db.Column(db.String(512))
    action = db.Column(db.String(50))  # 'read', 'write', 'delete', 'other'


class ServerConfig(db.Model):
    __tablename__ = 'server_config'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    hostname = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
