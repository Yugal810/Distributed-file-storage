from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True) # Added for your Profile UI
    email = Column(String, unique=True, index=True)
    password = Column(String)
    
    folders = relationship("Folder", back_populates="owner", cascade="all, delete-orphan")
    files = relationship("File", back_populates="owner", cascade="all, delete-orphan")

class Folder(Base):
    __tablename__ = "folders"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # ondelete="CASCADE" ensures the DB level link is broken
    parent_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True) 
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="folders")
    # This cascade ensures files inside the folder are deleted when the folder is deleted
    files = relationship("File", back_populates="folder", cascade="all, delete-orphan")
    
    # Self-referential relationship for subfolders
    subfolders = relationship(
        "Folder", 
        backref="parent", 
        remote_side=[id], 
        cascade="all, delete-orphan"
    )

class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    size = Column(Integer, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="files")
    folder = relationship("Folder", back_populates="files")
    # This cascade ensures shards (chunks) are deleted when the file record is deleted
    chunks = relationship("FileChunk", back_populates="file", cascade="all, delete-orphan")

class FileChunk(Base):
    __tablename__ = "file_chunks"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))
    chunk_index = Column(Integer)
    node = Column(String) 

    file = relationship("File", back_populates="chunks")

# SharedLink remains the same, but added cascade just in case
class SharedLink(Base):
    __tablename__ = "shared_links"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"))
    share_token = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    expires_at = Column(DateTime)

    file = relationship("File")