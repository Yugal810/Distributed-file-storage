from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import os

from ..database import get_db
from .. import models, auth

router = APIRouter(tags=["Files"])

# Configuration
NODES = ["storage_nodes/node1", "storage_nodes/node2", "storage_nodes/node3"]
CHUNK_SIZE = 1024 * 1024  # 1MB
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Ensure storage directories exist
for node in NODES:
    os.makedirs(node, exist_ok=True)

# --- Dependency: Get Current User from JWT ---
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- Helper: Cleanup Temp Files ---
def remove_file(path: str):
    if os.path.exists(path):
        os.remove(path)

# --- Route: Upload File (Sharded) ---
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    folder_id: int = None, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Read file data
    file_data = await file.read()

    # 2. Create file entry in DB linked to user and folder
    db_file = models.File(
        filename=file.filename,
        owner_id=current_user.id,
        folder_id=folder_id
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # 3. Split into chunks
    chunks = [file_data[i:i+CHUNK_SIZE] for i in range(0, len(file_data), CHUNK_SIZE)]
    chunk_locations = []

    # 4. Distribute chunks across nodes
    for i, chunk in enumerate(chunks):
        node = NODES[i % len(NODES)]
        chunk_name = f"file_{db_file.id}_chunk_{i}" # Unique naming
        path = os.path.join(node, chunk_name)

        with open(path, "wb") as f:
            f.write(chunk)

        # 5. Save chunk metadata
        db_chunk = models.FileChunk(
            file_id=db_file.id,
            chunk_index=i,
            node=node
        )
        db.add(db_chunk)
        chunk_locations.append(path)

    db.commit()

    return {
        "message": "File uploaded successfully",
        "file_id": db_file.id,
        "filename": file.filename,
        "total_chunks": len(chunks)
    }

# --- Route: Download File (Reassemble) ---
@router.get("/download/{file_id}")
def download_file(
    file_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Verify file exists and belongs to user
    db_file = db.query(models.File).filter(
        models.File.id == file_id, 
        models.File.owner_id == current_user.id
    ).first()

    if not db_file:
        raise HTTPException(status_code=404, detail="File not found or access denied")

    # 2. Fetch all chunks in order
    chunks = (
        db.query(models.FileChunk)
        .filter(models.FileChunk.file_id == file_id)
        .order_by(models.FileChunk.chunk_index)
        .all()
    )

    if not chunks:
        raise HTTPException(status_code=404, detail="File data missing")

    # 3. Reassemble chunks into a temporary file
    output_path = f"temp_{db_file.id}_{db_file.filename}"
    
    with open(output_path, "wb") as output_file:
        for chunk in chunks:
            chunk_path = os.path.join(chunk.node, f"file_{db_file.id}_chunk_{chunk.chunk_index}")
            
            if not os.path.exists(chunk_path):
                raise HTTPException(status_code=500, detail=f"Missing chunk {chunk.chunk_index}")
                
            with open(chunk_path, "rb") as f:
                output_file.write(f.read())

    # 4. Send file and cleanup temp file afterwards
    background_tasks.add_task(remove_file, output_path)
    
    return FileResponse(
        path=output_path, 
        filename=db_file.filename,
        media_type='application/octet-stream'
    )

@router.delete("/delete/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Find the file and verify ownership
    db_file = db.query(models.File).filter(
        models.File.id == file_id, 
        models.File.owner_id == current_user.id
    ).first()

    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    # 2. Find and delete physical chunks from the hard drive
    chunks = db.query(models.FileChunk).filter(models.FileChunk.file_id == file_id).all()
    for chunk in chunks:
        chunk_path = os.path.join(chunk.node, f"file_{file_id}_chunk_{chunk.chunk_index}")
        if os.path.exists(chunk_path):
            os.remove(chunk_path)

    # 3. Delete from database (Cascade will handle FileChunks if set up in models)
    db.delete(db_file)
    db.commit()

    return {"detail": f"File {file_id} and its shards successfully deleted"}

@router.patch("/{file_id}/move")
def move_file(file_id: int, folder_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    file = db.query(models.File).filter(models.File.id == file_id, models.File.owner_id == current_user.id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Update the folder location
    file.folder_id = folder_id
    db.commit()
    return {"message": f"Moved {file.filename} to folder {folder_id}"}

@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    folder = db.query(models.Folder).filter(models.Folder.id == folder_id, models.Folder.owner_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    db.delete(folder) # If your models have cascade="all, delete", this wipes subfolders/files too
    db.commit()
    return {"message": "Folder deleted"}