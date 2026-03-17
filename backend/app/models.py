from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .database import Base
import uuid


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    
    folders = relationship("Folder", back_populates="owner")
    files = relationship("File", back_populates="owner")

class Folder(Base):
    __tablename__ = "folders"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True) 
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="folders")
    files = relationship("File", back_populates="folder")

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    # Recommended additions:
    size = Column(Integer, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="files")
    folder = relationship("Folder", back_populates="files")
    chunks = relationship("FileChunk", back_populates="file", cascade="all, delete-orphan")

class FileChunk(Base):
    __tablename__ = "file_chunks"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))
    chunk_index = Column(Integer)  # 0, 1, 2...
    node = Column(String)         # e.g., "storage_nodes/node1"

    file = relationship("File", back_populates="chunks")

class SharedLink(Base):
    __tablename__ = "shared_links"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))
    share_token = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    expires_at = Column(DateTime)

    file = relationship("File")