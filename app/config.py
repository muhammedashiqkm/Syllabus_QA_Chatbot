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
        
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 24)))

    # AI Model Configuration
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "models/text-embedding-004")

    # --- LLM Provider Settings ---

    # Google Gemini
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
    
    # DeepSeek (uses OpenAI-compatible API)
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL_NAME = os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    
    # ADDED: Configurable text chunking parameters
    TEXT_CHUNK_SIZE = int(os.getenv("TEXT_CHUNK_SIZE", 1000))
    TEXT_CHUNK_OVERLAP = int(os.getenv("TEXT_CHUNK_OVERLAP", 200))

    CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", 10))

    # Celery Configuration
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'