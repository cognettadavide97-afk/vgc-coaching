from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.users import User
from backend.schemas.users import UserCreate, UserResponse
from typing import List

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()

@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    # controlla se l'email esiste già
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        return existing  # restituisce l'utente esistente invece di creare un duplicato

    db_user = User(
        nome=user.nome,
        email=user.email,
        telefono=user.telefono,
        showdown_username=user.showdown_username
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user