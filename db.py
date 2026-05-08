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


class AppSetting(db.Model):
    __tablename__ = 'app_setting'

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(255), nullable=False)


def get_setting(key, default=None):
    s = db.session.get(AppSetting, key)
    return s.value if s else default


class WatchPath(db.Model):
    __tablename__ = 'watch_path'

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(1024), nullable=False)  # e.g. D:\Data\
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AccountFilter(db.Model):
    __tablename__ = 'account_filter'

    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(255), nullable=False)  # e.g. DOMEIN\* or *\jan*
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProcessFilter(db.Model):
    __tablename__ = 'process_filter'

    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(255), nullable=False)  # e.g. svchost.exe or *update*
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ServerConfig(db.Model):
    __tablename__ = 'server_config'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    hostname = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
