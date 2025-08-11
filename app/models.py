import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ... (User, Syllabus, ClassModel, Subject models are unchanged) ...

class User(db.Model):
    """Represents a regular end-user for the chat API."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Syllabus(db.Model):
    __tablename__ = "syllabuses"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    def __str__(self):
        return self.name

class ClassModel(db.Model):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    def __str__(self):
        return self.name

class Subject(db.Model):
    __tablename__ = "subjects"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    def __str__(self):
        return self.name

class Document(db.Model):
    """Represents a single PDF document, linked to categories."""
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # --- NEW FIELDS ---
    processing_status = Column(String(20), default='PENDING', nullable=False)
    processing_time_ms = Column(Integer, nullable=True)
    
    syllabus_id = Column(Integer, ForeignKey("syllabuses.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)

    syllabus = db.relationship("Syllabus")
    class_model = db.relationship("ClassModel")
    subject = db.relationship("Subject")
    
    def __str__(self):
        return f"{self.subject.name} - {self.class_model.name} ({self.syllabus.name})"


class DocumentChunk(db.Model):
    """Represents a text chunk and its vector embedding."""
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768))
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    document = db.relationship("Document")


class ChatHistory(db.Model):
    """Stores conversation history for each user session."""
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True)
    chatbot_user_id = Column(String, index=True, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())