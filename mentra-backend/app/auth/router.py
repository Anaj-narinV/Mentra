from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.errors import ConflictError, UnauthorizedError
from app.models.models import User, Profile
from app.schemas.schemas import SignupRequest, LoginRequest, AuthResponse, OkResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise ConflictError("An account with this email already exists.")
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id))
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return {"token": token, "user": user}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("That email/password doesn't match — try again.")
    token = create_access_token(user.id)
    return {"token": token, "user": user}


@router.post("/logout", response_model=OkResponse)
def logout():
    # Stateless JWT: nothing to invalidate server-side for MVP; the client
    # discards the token. (Token blacklisting can be added later if needed.)
    return {"ok": True}
