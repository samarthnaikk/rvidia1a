from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/google-login")
def google_login_disabled():
    raise HTTPException(status_code=410, detail="Google authentication is disabled for MVP")