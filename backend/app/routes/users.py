from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from .. import models, auth, database

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- 1. SIGNUP ROUTE ---
@router.post("/signup")
def signup(
    email: str, 
    password: str, 
    name: Optional[str] = None, 
    db: Session = Depends(database.get_db)
):
    """
    Creates a new user. Hashes the password before saving to PostgreSQL.
    """
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email already registered"
        )
    
    # Hash the password using your auth utility
    hashed_pwd = auth.hash_password(password)
    
    # Create the user record
    new_user = models.User(
        email=email, 
        password=hashed_pwd, 
        name=name if name else email.split('@')[0].capitalize()
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User created successfully", "user_id": new_user.id}

# --- 2. LOGIN ROUTE ---
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(database.get_db)
):
    """
    Validates credentials and returns a JWT Access Token.
    Note: form_data.username is actually the user's email here.
    """
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    if not user or not auth.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create the JWT
    access_token = auth.create_access_token(data={"sub": user.email})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer"
    }

# --- 3. GET CURRENT USER (For Profile UI) ---
@router.get("/me")
def get_me(
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Returns the logged-in user's details for the React Dashboard header.
    Requires a valid 'Authorization: Bearer <token>' header.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": getattr(current_user, "name", current_user.email.split('@')[0].capitalize())
    }