from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from .. import models
from .files import get_current_user

router = APIRouter(prefix="/folders", tags=["Folders"])

# --- CREATE FOLDER ---
@router.post("/")
def create_folder(
    name: str, 
    parent_id: Optional[int] = None, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """Creates a folder. If parent_id is provided, it becomes a subfolder."""
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
    """Returns the full flat list of folders and files for the user."""
    folders = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id).all()
    files = db.query(models.File).filter(models.File.owner_id == current_user.id).all()

    return {
        "folders": [
            {
                "id": f.id, 
                "name": f.name, 
                "parent_id": f.parent_id
            } for f in folders
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

# --- DELETE FOLDER (THE MISSING PIECE) ---
@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Deletes a specific folder and prevents orphans."""
    # 1. Find the folder
    folder = db.query(models.Folder).filter(
        models.Folder.id == folder_id, 
        models.Folder.owner_id == current_user.id
    ).first()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # 2. Delete the folder 
    # (Note: If your database has cascade delete set up in models.py, 
    # it will automatically clean up subfolders and file references)
    db.delete(folder)
    db.commit()
    
    return {"message": f"Folder {folder_id} deleted successfully"}