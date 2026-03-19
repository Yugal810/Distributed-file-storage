import os
import boto3
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from .. import models
from .files import get_current_user

router = APIRouter(prefix="/folders", tags=["Folders"])

# --- S3 Configuration (To clean up shards) ---
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)
BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")

# --- CREATE FOLDER ---
@router.post("/")
def create_folder(
    name: str, 
    parent_id: Optional[int] = None, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    if parent_id:
        parent = db.query(models.Folder).filter(
            models.Folder.id == parent_id, 
            models.Folder.owner_id == current_user.id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found")

    new_folder = models.Folder(
        name=name, 
        parent_id=parent_id, 
        owner_id=current_user.id
    )
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder

# --- EXPLORER (GET ALL) ---
@router.get("/explorer")
def get_user_storage_explorer(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    folders = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id).all()
    files = db.query(models.File).filter(models.File.owner_id == current_user.id).all()

    return {
        "folders": [
            {"id": f.id, "name": f.name, "parent_id": f.parent_id} for f in folders
        ],
        "organized_files": [
            {
                "id": file.id, 
                "name": file.filename, 
                "folder_id": file.folder_id,
                "size": file.size,
                "created_at": file.created_at
            } for file in files if file.folder_id is not None
        ],
        "root_files": [
            {
                "id": file.id, 
                "name": file.filename,
                "size": file.size
            } for file in files if file.folder_id is None
        ]
    }

# --- DELETE FOLDER (With S3 Cleanup) ---
@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Find the folder
    folder = db.query(models.Folder).filter(
        models.Folder.id == folder_id, 
        models.Folder.owner_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # 2. Find all files that belong to this folder (to clean S3)
    # This also finds files in sub-folders if you want to be thorough
    files_to_wipe = db.query(models.File).filter(models.File.folder_id == folder_id).all()

    # 3. Physically delete shards from S3 nodes
    for file in files_to_wipe:
        chunks = db.query(models.FileChunk).filter(models.FileChunk.file_id == file.id).all()
        for chunk in chunks:
            s3_key = f"{chunk.node}/file_{file.id}_chunk_{chunk.chunk_index}"
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
            except Exception as e:
                print(f"S3 Delete Error for {s3_key}: {e}")

    # 4. Delete the folder from DB
    # If your models.py has cascade="all, delete-orphan", 
    # the File records will be deleted automatically here.
    db.delete(folder)
    db.commit()
    
    return {"message": f"Folder {folder.name} and all its sharded contents deleted successfully"}