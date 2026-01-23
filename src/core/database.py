"""
Database Models and Connection
SQLAlchemy models for sites and devices persistence
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, JSON, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, relationship, DeclarativeBase
from sqlalchemy.pool import StaticPool
import os

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class SiteModel(Base):
    """Site database model"""
    __tablename__ = "sites"

    site_id = Column(String(100), primary_key=True)
    site_name = Column(String(200), nullable=False)
    location = Column(String(500))
    timezone = Column(String(100))
    climate = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    country = Column(String(100))
    state = Column(String(100))
    settings = Column(JSON)  # Store settings as JSON
    devices_config = Column(JSON)  # Store devices config as JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    devices = relationship("DeviceModel", back_populates="site", cascade="all, delete-orphan")


class DeviceModel(Base):
    """Device database model"""
    __tablename__ = "devices"

    device_id = Column(String(100), primary_key=True)
    device_type = Column(String(50), nullable=False)
    integration_name = Column(String(100))
    status = Column(String(50), default="registered")
    site_id = Column(String(100), ForeignKey("sites.site_id"), nullable=True)
    device_metadata = Column("metadata", JSON)  # Use device_metadata as attribute name, but keep "metadata" as column name
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    site = relationship("SiteModel", back_populates="devices")


class Database:
    """Database connection and session management"""

    def __init__(self, database_url: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize database connection

        Args:
            database_url: Database URL (e.g., postgresql://user:pass@host:port/db)
                         If None, will try to construct from environment variables or config
            config: Optional configuration dictionary with database settings
        """
        if database_url is None:
            # Try to get from config first
            if config:
                db_host = config.get("host", "localhost")
                db_port = config.get("port", 5432)
                db_user = config.get("user", "bess_agent")
                db_password = config.get("password", "")
                db_name = config.get("database", "bess_agent")
            else:
                # Try to get from environment variables
                db_host = os.getenv("DB_HOST", "localhost")
                db_port = os.getenv("DB_PORT", "5432")
                db_user = os.getenv("DB_USER", "bess_agent")
                db_password = os.getenv("DB_PASSWORD", "")
                db_name = os.getenv("DB_NAME", "bess_agent")
            
            if db_password:
                database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            else:
                # Fallback to SQLite for development
                logger.warning("No database password found, using SQLite for development")
                database_url = "sqlite:///./data/bess_agent.db"
        
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

    def initialize(self):
        """Initialize database connection and create tables"""
        try:
            # Create engine
            if self.database_url.startswith("sqlite"):
                # SQLite specific configuration
                self.engine = create_engine(
                    self.database_url,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                # PostgreSQL configuration
                self.engine = create_engine(
                    self.database_url,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                )
            
            # Create session factory
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            
            self._initialized = True
            logger.info(f"✓ Database initialized: {self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise

    def get_session(self) -> Session:
        """Get database session"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()

    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")


# Global database instance
_db_instance: Optional[Database] = None


def get_database(database_url: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> Database:
    """Get or create database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(database_url, config)
        _db_instance.initialize()
    return _db_instance


def get_db_session() -> Session:
    """Get database session (for dependency injection)"""
    db = get_database()
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()











