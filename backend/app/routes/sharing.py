from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import uuid
from fastapi import BackgroundTasks

from ..database import get_db
from .. import models
from .files import get_current_user # To verify who is creating the link

router = APIRouter(prefix="/share", tags=["Sharing"])

# ROUTE 1: Generate the link (Requires Login)
@router.post("/{file_id}")
def generate_share_link(
    file_id: int, 
    expires_in_hours: int = 24, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    file = db.query(models.File).filter(models.File.id == file_id, models.File.owner_id == current_user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    expiration = datetime.utcnow() + timedelta(hours=expires_in_hours)
    # This creates the unique UUID token
    new_link = models.SharedLink(file_id=file_id, expires_at=expiration)
    
    db.add(new_link)
    db.commit()
    db.refresh(new_link)

    return {
        "share_url": f"http://127.0.0.1:8000/share/download/{new_link.share_token}",
        "expires_at": expiration
    }

# ROUTE 2: The actual download (Public - No Login Required)
@router.get("/download/{token}")
def download_shared_file(token: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    link = db.query(models.SharedLink).filter(models.SharedLink.share_token == token).first()
    
    if not link or link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Link expired or invalid")

    file_record = db.query(models.File).filter(models.File.id == link.file_id).first()
    chunks = db.query(models.FileChunk).filter(models.FileChunk.file_id == file_record.id).order_by(models.FileChunk.chunk_index).all()
    
    temp_file_path = f"temp_shared_{file_record.filename}"
    with open(temp_file_path, "wb") as f_out:
        for chunk in chunks:
            chunk_path = os.path.join(chunk.node, f"file_{file_record.id}_chunk_{chunk.chunk_index}")
            if os.path.exists(chunk_path):
                with open(chunk_path, "rb") as f_in:
                    f_out.write(f_in.read())
    background_tasks.add_task(os.remove, temp_file_path)
    return FileResponse(temp_file_path, filename=file_record.filename)