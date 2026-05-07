import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///fileserver.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '30'))
