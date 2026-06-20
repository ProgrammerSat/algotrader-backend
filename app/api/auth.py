"""
Auth routes: Register, Login (JWT), Fyers OAuth, Fyers callback.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import bcrypt

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.fyers_client import build_auth_url, exchange_code_for_token, set_fyers_client
from app.core.config import get_settings
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=_hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(access_token=token, user_id=user.id, email=user.email, full_name=user.full_name)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or not _verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        fyers_linked=user.fyers_linked,
    )


@router.get("/fyers/initiate")
def fyers_login():
    """Return the Fyers OAuth URL for the user to open."""
    url = build_auth_url()
    return {"auth_url": url}


@router.post("/fyers/link")
def fyers_link_manual(
    auth_code: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manual auth code exchange.
    User visits the Fyers OAuth URL, authorises, and Fyers redirects to Google.
    They copy the `auth_code` query param from the Google URL and paste it here.
    """
    try:
        access_token = exchange_code_for_token(auth_code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    current_user.fyers_access_token = access_token
    current_user.fyers_linked = True
    db.commit()
    set_fyers_client(access_token)
    return {"detail": "Fyers account linked successfully", "fyers_linked": True}



