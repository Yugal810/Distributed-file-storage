from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
import os
import boto3
from datetime import datetime 
from dotenv import load_dotenv

from ..database import get_db
from .. import models, auth

load_dotenv()

router = APIRouter(tags=["Files"])

# --- AWS Configuration ---
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)
BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")

# We treat S3 "folders" as our nodes
NODES = ["node1", "node2", "node3"]
CHUNK_SIZE = 1024 * 1024  # 1MB
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- Dependency: Get Current User ---
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

# Helper to clean up the reassembled temp file after download
def remove_file(path: str):
    if os.path.exists(path):
        os.remove(path)

# --- Route: Upload File (To S3) ---
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    folder_id: int = None, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    file_data = await file.read()

    # 1. Database Entry
    db_file = models.File(
        filename=file.filename,
        owner_id=current_user.id,
        folder_id=folder_id,
        size=len(file_data),             
        created_at=datetime.utcnow()
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # 2. Sharding
    chunks = [file_data[i:i+CHUNK_SIZE] for i in range(0, len(file_data), CHUNK_SIZE)]

    # 3. Distribute to S3 Nodes
    for i, chunk in enumerate(chunks):
        node = NODES[i % len(NODES)]
        chunk_name = f"file_{db_file.id}_chunk_{i}"
        s3_key = f"{node}/{chunk_name}" # Path inside S3 bucket

        # Upload chunk to S3
        s3_client.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=chunk)

        # 4. Save metadata
        db_chunk = models.FileChunk(
            file_id=db_file.id,
            chunk_index=i,
            node=node # Storing 'node1', 'node2', etc.
        )
        db.add(db_chunk)

    db.commit()

    return {
        "message": "File uploaded to S3 successfully",
        "file_id": db_file.id,
        "total_chunks": len(chunks)
    }

# --- Route: Download (Reassemble from S3) ---
@router.get("/download/{file_id}")
def download_file(
    file_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_file = db.query(models.File).filter(
        models.File.id == file_id, 
        models.File.owner_id == current_user.id
    ).first()

    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    chunks = db.query(models.FileChunk).filter(models.FileChunk.file_id == file_id).order_by(models.FileChunk.chunk_index).all()

    output_path = f"temp_{db_file.id}_{db_file.filename}"
    
    with open(output_path, "wb") as output_file:
        for chunk in chunks:
            s3_key = f"{chunk.node}/file_{db_file.id}_chunk_{chunk.chunk_index}"
            
            # Fetch chunk from S3
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            output_file.write(response['Body'].read())

    background_tasks.add_task(remove_file, output_path)
    
    return FileResponse(path=output_path, filename=db_file.filename)

# --- Route: Delete (From S3) ---
@router.delete("/delete/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    db_file = db.query(models.File).filter(models.File.id == file_id, models.File.owner_id == current_user.id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    chunks = db.query(models.FileChunk).filter(models.FileChunk.file_id == file_id).all()
    for chunk in chunks:
        s3_key = f"{chunk.node}/file_{file_id}_chunk_{chunk.chunk_index}"
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)

    db.delete(db_file)
    db.commit()

    return {"detail": "File and S3 shards deleted"}