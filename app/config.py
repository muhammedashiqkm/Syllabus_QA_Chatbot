import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration settings."""

    # Flask Secret Key for session management and security
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY found in environment variables. This is required for security.")

    # Secret key required to register the first admin user
    REGISTRATION_SECRET_KEY = os.getenv("REGISTRATION_SECRET_KEY")
    if not REGISTRATION_SECRET_KEY:
        raise ValueError("No REGISTRATION_SECRET_KEY found in environment variables.")

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("No DATABASE_URL found in environment variables")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    #Rate Limiter Storage URI 
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memcached://memcached:11211")
    if not RATELIMIT_STORAGE_URI:
        raise ValueError("No RATELIMIT_STORAGE_URI found in environment variables.")
    

    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")
    
    # Google API Key
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("No GOOGLE_API_KEY found in environment variables")

    # JWT Configuration
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    if not JWT_SECRET_KEY:
        raise ValueError("No JWT_SECRET_KEY found in environment variables")
        
    # Load token expiration from .env in HOURS, defaulting to 24 hours.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 24)))

    # AI Model Configuration
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "models/text-embedding-004")
    LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash")