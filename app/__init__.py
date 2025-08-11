import logging
import click
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import ValidationError
from concurrent.futures import ThreadPoolExecutor

from app.config import Config
from app.models import db, User
from app.logging_config import setup_logging
from app.exceptions import ApiError
from app.admin import setup_admin

# Initialize extensions
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

def create_app():
    """Application factory function."""
    setup_logging()
    access_logger = logging.getLogger('access')

    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure a simple thread pool for background tasks
    app.config['EXECUTOR'] = ThreadPoolExecutor(max_workers=2)

    # Initialize extensions with the app object
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    setup_admin(app) # Setup the admin panel

    # --- Register Blueprints ---
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # --- CLI Commands ---
    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("password")
    def create_user(username, password):
        """Creates a new end-user for the API."""
        if User.query.filter_by(username=username).first():
            print(f"User '{username}' already exists.")
            return
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"User '{username}' created successfully.")

    # --- Request Logging ---
    @app.before_request
    def log_request_info():
        if not request.path.startswith('/static'): # Don't log static file requests
            access_logger.info(f"Request: {request.method} {request.path} - IP: {request.remote_addr}")

    # --- Custom Error Handlers ---
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation(err):
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400
    
    # ... (other error handlers: 404, 500, 401, 429) remain the same

    return app