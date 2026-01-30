from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os
from datetime import timedelta

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app(config_class=None):
    app = Flask(__name__)
    
    # Load configuration
    if config_class:
        app.config.from_object(config_class)
    else:
        app.config.from_pyfile('../config.py')
    
    # Ensure models are loaded for migrations
    from app import models
    
    # Override with environment variables if available
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', app.config.get('SECRET_KEY'))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', app.config.get('SQLALCHEMY_DATABASE_URI'))
    
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Security Extensions

    from flask_talisman import Talisman
    
    # Register Blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.products import products_bp
    from app.routes.sales import sales_bp
    from app.routes.pos import pos_bp 
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.expenses import expenses_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(sales_bp, url_prefix='/sales')
    app.register_blueprint(pos_bp, url_prefix='/pos')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp)
    app.register_blueprint(expenses_bp, url_prefix='/expenses')

    

    
    # Content Security Policy
    csp = {
        'default-src': '\'self\'',
        'script-src': ['\'self\'', 'https://cdn.jsdelivr.net', '\'unsafe-inline\''], # unsafe-inline needed for some JS interaction, refrain if possible in strict mode but necessary for bootstrap/custom scripts often
        'style-src': ['\'self\'', 'https://cdn.jsdelivr.net', '\'unsafe-inline\''],
        'img-src': ['\'self\'', 'data:', 'https:'],
        'font-src': ['\'self\'', 'https://cdn.jsdelivr.net', 'https://fonts.gstatic.com']
    }
    
    Talisman(app, content_security_policy=csp, force_https=False) # force_https=False for local dev
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        # Import inside function to avoid circular imports if needed,
        # though models is already imported in create_app
        from app.models import User
        return User.query.get(int(user_id))
    

    
    # Register template filters
    from app.utils import format_currency
    app.jinja_env.filters['format_currency'] = format_currency
    app.jinja_env.globals.update(format_currency=format_currency) # Register as global function
    
    # Register context processors
    from app.context_processors import inject_global_context
    app.context_processor(inject_global_context)
    
    # Register CLI commands
    from app.cli import cli
    app.cli.add_command(cli)
    
    # Add error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        # Return JSON for AJAX requests
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Access forbidden'}), 403
        return render_template('errors/403.html'), 403
    
    return app





