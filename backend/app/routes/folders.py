from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models
from .files import get_current_user

router = APIRouter(prefix="/folders", tags=["Folders"])

@router.post("/")
def create_folder(name: str, parent_id: int = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_folder = models.Folder(name=name, parent_id=parent_id, owner_id=current_user.id)
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder

@router.get("/")
def list_my_storage(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # Returns all root-level folders and files for the user
    folders = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id, models.Folder.parent_id == None).all()
    files = db.query(models.File).filter(models.File.owner_id == current_user.id, models.File.folder_id == None).all()
    return {"folders": folders, "files": files}

@router.get("/explorer")
def get_user_storage(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Fetch all folders and files for this user
    folders = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id).all()
    files = db.query(models.File).filter(models.File.owner_id == current_user.id).all()

    # 2. Build a simple response structure
    return {
        "folders": [
            {
                "id": f.id, 
                "name": f.name, 
                "parent_id": f.parent_id
            } for f in folders
        ],
        "root_files": [
            {
                "id": file.id, 
                "name": file.filename, 
                "folder_id": file.folder_id
            } for file in files if file.folder_id is None
        ],
        "organized_files": [
            {
                "id": file.id, 
                "name": file.filename, 
                "folder_id": file.folder_id
            } for file in files if file.folder_id is not None
        ]
    }