from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize SQLAlchemy without an app object
db = SQLAlchemy()

class User(db.Model):
    """
    Represents a user who can register and log in.
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    def set_password(self, password):
        """Hashes the password and stores it."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the hash."""
        return check_password_hash(self.password_hash, password)

class Subject(db.Model):
    """
    Represents a subject, which is a processed PDF document.
    """
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True, index=True)
    subject_key = Column(String, unique=True, index=True, nullable=False)
    source_url = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DocumentChunk(db.Model):
    """
    Represents a single chunk of text from a subject and its vector embedding.
    """
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768)) 

class ChatHistory(db.Model):
    """
    Stores the history of questions and answers for each user.
    """
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    subject_key = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
