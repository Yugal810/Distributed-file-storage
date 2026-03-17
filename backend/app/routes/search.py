from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database import get_db
from .. import models
from .files import get_current_user

router = APIRouter(prefix="/search", tags=["Search"])

@router.get("/")
def search_all(
    query: str, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    """
    Search for files and folders belonging to the current user.
    Matches any part of the name (case-insensitive).
    """
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters.")

    # 1. Search Files (checks filename)
    files = db.query(models.File).filter(
        models.File.owner_id == current_user.id,
        models.File.filename.ilike(f"%{query}%")
    ).all()

    # 2. Search Folders (checks folder name)
    folders = db.query(models.Folder).filter(
        models.Folder.owner_id == current_user.id,
        models.Folder.name.ilike(f"%{query}%")
    ).all()

    return {
        "search_term": query,
        "results": {
            "folders": [
                {
                    "id": folder.id, 
                    "name": folder.name, 
                    "parent_id": folder.parent_id
                } for folder in folders
            ],
            "files": [
                {
                    "id": file.id, 
                    "name": file.filename, 
                    "folder_id": file.folder_id
                } for file in files
            ]
        },
        "total_hits": len(files) + len(folders)
    }