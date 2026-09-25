from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.models.models import User, Profile
from app.schemas.schemas import ProfileIn, ProfileOut, OkResponse

router = APIRouter(tags=["profile"])


def _get_or_create_profile(db: Session, user: User) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_or_create_profile(db, user)


def _apply(profile: Profile, payload: ProfileIn):
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(profile, key, value)


@router.put("/profile", response_model=ProfileOut)
def update_profile(payload: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, user)
    _apply(profile, payload)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/onboarding", response_model=OkResponse)
def complete_onboarding(payload: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    profile = _get_or_create_profile(db, user)
    _apply(profile, payload)
    profile.onboarding_complete = True
    db.commit()
    return {"ok": True}
