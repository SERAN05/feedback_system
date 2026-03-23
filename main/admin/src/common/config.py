import os


def _env_to_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _env_to_int(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_secret_key_here'
    _db_url = os.environ.get('DATABASE_URL') or os.environ.get('MYSQL_URL')
    if _db_url and _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    if _db_url and _db_url.startswith('mysql://'):
        _db_url = _db_url.replace('mysql://', 'mysql+pymysql://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url or 'mysql+pymysql://root:password@localhost/course_feedback'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

    # Email notifications for event start
    SMTP_HOST = os.environ.get('SMTP_HOST')
    SMTP_PORT = _env_to_int('SMTP_PORT', 587)
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    SMTP_USE_TLS = _env_to_bool('SMTP_USE_TLS', True)
    SMTP_USE_SSL = _env_to_bool('SMTP_USE_SSL', False)
    SMTP_TIMEOUT = _env_to_int('SMTP_TIMEOUT', 30)
    MAIL_FROM = os.environ.get('MAIL_FROM') or SMTP_USERNAME
    STUDENT_LOGIN_URL = os.environ.get('STUDENT_LOGIN_URL')
