import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """Configures logging for the application."""
    
    log_directory = 'app/logs'

    # Create logs directory inside 'app' folder if it doesn't exist
    os.makedirs(log_directory, exist_ok=True)

    # --- Formatter ---
    # A consistent format for all log messages
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- Handlers ---
    # Define file handlers with the new path
    app_handler = RotatingFileHandler(f'{log_directory}/app.log', maxBytes=10485760, backupCount=5)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(f'{log_directory}/error.log', maxBytes=10485760, backupCount=5)
    error_handler.setFormatter(formatter)

    access_handler = RotatingFileHandler(f'{log_directory}/access.log', maxBytes=10485760, backupCount=5)
    access_handler.setFormatter(formatter)
    
    security_handler = RotatingFileHandler(f'{log_directory}/security.log', maxBytes=10485760, backupCount=5)
    security_handler.setFormatter(formatter)

    # --- Loggers ---
    # Get logger instances. These names can be used throughout the app.
    
    # General application logger
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(app_handler)

    # Logger for critical errors and exceptions
    error_logger = logging.getLogger('error')
    error_logger.setLevel(logging.ERROR)
    error_logger.addHandler(error_handler)

    # Logger for incoming requests
    access_logger = logging.getLogger('access')
    access_logger.setLevel(logging.INFO)
    access_logger.addHandler(access_handler)
    
    # Logger for security-related events (login, registration, etc.)
    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.INFO)
    security_logger.addHandler(security_handler)
