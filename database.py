"""
Database — SQLite database setup and SQLAlchemy ORM models.
Provides lightweight persistence for sessions, chat logs, flashcards, and tasks.
"""

import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./study_companion.db"

# Create engine and session factory
# connect_args={"check_same_thread": False} is required for SQLite in concurrent setups
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class StudySession(Base):
    __tablename__ = "study_sessions"

    session_id = Column(String, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    char_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    flashcards = relationship("Flashcard", back_populates="session", cascade="all, delete-orphan")
    tasks = relationship("GenerationTask", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("study_sessions.session_id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'ai'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("StudySession", back_populates="messages")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, ForeignKey("study_sessions.session_id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("StudySession", back_populates="flashcards")


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    task_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("study_sessions.session_id"), nullable=False)
    asset_type = Column(String, nullable=False)  # 'pdf', 'ppt', 'audio', 'flashcards'
    status = Column(String, default="processing")  # 'processing', 'completed', 'failed'
    file_url = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("StudySession", back_populates="tasks")


def init_db():
    """Create all tables in the SQLite database."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency generator to yield database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
