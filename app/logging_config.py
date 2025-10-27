import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    """Configures logging for the application."""
    
    log_directory = 'logs'

    os.makedirs(log_directory, exist_ok=True)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    app_handler = RotatingFileHandler(f'{log_directory}/app.log', maxBytes=10485760, backupCount=5)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(f'{log_directory}/error.log', maxBytes=10485760, backupCount=5)
    error_handler.setFormatter(formatter)

    access_handler = RotatingFileHandler(f'{log_directory}/access.log', maxBytes=10485760, backupCount=5)
    access_handler.setFormatter(formatter)
    
    security_handler = RotatingFileHandler(f'{log_directory}/security.log', maxBytes=10485760, backupCount=5)
    security_handler.setFormatter(formatter)

   
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(app_handler)

    error_logger = logging.getLogger('error')
    error_logger.setLevel(logging.ERROR)
    error_logger.addHandler(error_handler)

    access_logger = logging.getLogger('access')
    access_logger.setLevel(logging.INFO)
    access_logger.addHandler(access_handler)
    
    
    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.INFO)
    security_logger.addHandler(security_handler)