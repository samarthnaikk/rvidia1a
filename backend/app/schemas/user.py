from pydantic import BaseModel, EmailStr

class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str

class LoginRequest(BaseModel):
    username_or_email: str
    password: str