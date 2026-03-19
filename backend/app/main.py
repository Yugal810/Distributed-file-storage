from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # <--- Add this import
from .database import engine
from . import models
from .routes import users, files, folders, sharing, search

app = FastAPI(title="Distributed File Storage API")

# 1. Define who is allowed to talk to your backend
origins = [
    "http://localhost:5173",  # Your React local dev server
    "http://127.0.0.1:5173",
    "https://distributed-file-storage-3g5k.onrender.com", # Your production URL
]

# 2. Add the Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows GET, POST, DELETE, etc.
    allow_headers=["*"], # Allows Authorization headers
)

# Create tables

models.Base.metadata.create_all(bind=engine)

# Register routers
app.include_router(users.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(sharing.router)
app.include_router(search.router)

@app.get("/")
def root():
    return {"message": "Distributed File Storage API running"}