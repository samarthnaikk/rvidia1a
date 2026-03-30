import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.routes.auth import get_current_user


def test_get_current_user_returns_401_on_invalid_token(db_session):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=credentials, db=db_session)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid or expired token"
