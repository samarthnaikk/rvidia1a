from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests

from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import create_access_token
from app.core.security import GOOGLE_CLIENT_ID

router = APIRouter()

class GoogleToken(BaseModel):
    token: str


@router.post("/google-login")
def google_login(data: GoogleToken):
    try:
        idinfo = id_token.verify_oauth2_token(
            data.token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        print("✅ VERIFIED TOKEN:", idinfo)

        email = idinfo.get("email")
        name = idinfo.get("name")
        google_id = idinfo.get("sub")

        db = SessionLocal()

        user = db.query(User).filter(User.email == email).first()

        if not user:
            user = User(
                username=name,
                email=email,
                google_id=google_id,
                auth_provider="google",
                password_hash=""  # no password
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_access_token({"sub": user.username})

        return {
            "access_token": token,
            "token_type": "bearer"
        }

    except Exception as e:
        print("❌ ERROR:", str(e))
        raise HTTPException(status_code=400, detail="Invalid Google token")