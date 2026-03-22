import os
from app import create_app
from config import config

# Get configuration from environment variable
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config[config_name])

if __name__ == '__main__':
    # Dev server binds to localhost only — use start_pos.bat (Waitress) for LAN access
    app.run(host='127.0.0.1', port=5000, debug=config_name == 'development')