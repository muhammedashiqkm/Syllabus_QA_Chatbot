import logging
import click
from flask import Flask, jsonify, request, redirect, url_for
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import ValidationError
from flask_migrate import Migrate
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect

from app.config import Config
from app.models import db, User
from app.logging_config import setup_logging
from app.exceptions import ApiError
from app import utils

# Initialize extensions
jwt = JWTManager()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=Config.RATELIMIT_STORAGE_URI
)
migrate = Migrate()
csrf = CSRFProtect()

def create_app():
    """Application factory function."""
    setup_logging()
    access_logger = logging.getLogger('access')

    app = Flask(__name__)
    app.config.from_object(Config)

    # --- ADDED: Configure Celery with the Flask App Config ---
    from app.celery_worker import celery
    celery.conf.update(
        broker_url=app.config['CELERY_BROKER_URL'],
        result_backend=app.config['CELERY_RESULT_BACKEND']
    )
    celery.conf.update(app.config)
    # ---------------------------------------------------------

    # Initialize extensions with the app object
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Local import to break the circle
    from app.admin import setup_admin
    setup_admin(app)

    # Configure GenAI client once on startup
    with app.app_context():
        utils.configure_genai()

    # --- Register Blueprints ---
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ORIGINS")}})

    # --- CLI Commands (no changes) ---
    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("password")
    def create_user(username, password):
        """Creates a new end-user for the API."""
        if User.query.filter_by(username=username).first():
            print(f"User '{username}' already exists.")
            return
        new_user = User(username=username, is_admin=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"User '{username}' created successfully.")

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.argument("password")
    def create_admin(username, password):
        """Creates a new admin user."""
        if User.query.filter_by(username=username).first():
            print(f"Admin user '{username}' already exists.")
            return
        new_user = User(username=username, is_admin=True)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        print(f"Admin user '{username}' created successfully.")

    @app.route("/")
    def index():
        """Redirects the base URL ('/') to the admin login page ('/admin')."""
        return redirect(url_for('admin.index'))

    # --- Request Logging & Error Handlers (no changes) ---
    @app.before_request
    def log_request_info():
        if not request.path.startswith('/static'):
            access_logger.info(f"Request: {request.method} {request.path} - IP: {request.remote_addr}")

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(ValidationError)
    def handle_marshmallow_validation(err):
        return jsonify({"error": "Validation failed", "messages": err.messages}), 400
    
    return app