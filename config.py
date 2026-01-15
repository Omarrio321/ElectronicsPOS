import os
from datetime import timedelta


def get_wkhtmltopdf_path():
    """Robustly find wkhtmltopdf executable"""
    # 1. Check environment variable
    env_path = os.environ.get('WKHTMLTOPDF_PATH')
    if env_path and os.path.isfile(env_path):
        return env_path
        
    # 2. Check common installation paths
    common_paths = [
        r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
        r'C:\Program Files\wkhtmltopdf\wkhtmltopdf.exe',
        r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
        r'C:\Program Files (x86)\wkhtmltopdf\wkhtmltopdf.exe',
    ]
    
    for path in common_paths:
        if os.path.isfile(path):
            return path
            
    # 3. Last resort fallback (even if file check fails, return the most likely one)
    return r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'

# GLOBAL SCOPE: Important for app.config.from_pyfile
WKHTMLTOPDF_PATH = get_wkhtmltopdf_path()

class Config:
    """Base configuration class"""
    
    # Secret key - validated at runtime
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    

    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:password@localhost/electronics_pos'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Remember me cookie
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    
    # Pagination
    ITEMS_PER_PAGE = 20
    
    # Upload settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # PDF settings
    PDF_OPTIONS = {
        'page-size': 'A4',
        'encoding': 'UTF-8',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
    }
    
    # Path to wkhtmltopdf executable
    WKHTMLTOPDF_PATH = WKHTMLTOPDF_PATH

    @staticmethod
    def validate_production_config():
        """Validate required environment variables for production"""
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY environment variable must be set for production")
        if not os.environ.get('ADMIN_PASSWORD'):
            raise ValueError("ADMIN_PASSWORD environment variable must be set")

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production configuration - validates env vars"""
    DEBUG = False
    
    def __init__(self):
        Config.validate_production_config()


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    SECRET_KEY = 'test-secret-key-for-testing'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'TEST_DATABASE_URL',
        'mysql+pymysql://root:password@localhost:3306/electronics_pos_test'
    )
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}