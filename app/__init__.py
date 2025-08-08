import logging
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import ValidationError

from app.config import Config
from app.models import db
from app.logging_config import setup_logging
from app.exceptions import ApiError

# Initialize extensions without app object
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

def create_app():
    """
    Application factory function.
    Configures and returns the Flask application instance.
    """
    # Setup logging first
    setup_logging()
    access_logger = logging.getLogger('access')

    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions with the app object
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    # --- Register Blueprints ---
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # --- Request Logging ---
    @app.before_request
    def log_request_info():
        """Log information about each incoming request."""
        access_logger.info(
            f"Request: {request.method} {request.path} - IP: {request.remote_addr}"
        )

    # --- Custom Error Handlers ---
    # This ensures that all errors are returned in a consistent JSON format.
    
    @app.errorhandler(ApiError)
    def handle_api_error(error):
        error_logger = logging.getLogger('error')
        error_logger.error(f"API Error: {error.message} - Status: {error.status_code}")
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation(err):
        """Handle Marshmallow validation errors for clean responses."""
        error_logger = logging.getLogger('error')
        error_logger.warning(f"Validation Error: {err.messages}")
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400

    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Not Found", "message": "The requested URL was not found on the server."}), 404

    @app.errorhandler(500)
    def internal_error(error):
        error_logger = logging.getLogger('error')
        error_logger.critical(f"Internal Server Error: {error}", exc_info=True)
        db.session.rollback() # Rollback the session in case of a DB error
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500
        
    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify({"error": "Unauthorized", "message": "Authentication is required and has failed or has not yet been provided."}), 401

    @app.errorhandler(429)
    def ratelimit_handler(e):
        security_logger = logging.getLogger('security')
        security_logger.warning(f"Rate limit exceeded for {request.remote_addr} on endpoint {request.path}")
        return jsonify(error=f"Rate limit exceeded: {e.description}"), 429

    return app
