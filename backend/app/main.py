from fastapi import FastAPI
from .database import engine
from . import models
from .routes import users, files,folders,sharing,search

app = FastAPI(title="Distributed File Storage API")

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