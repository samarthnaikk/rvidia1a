from fastapi import FastAPI
from app.core.database import Base, engine
from app.routes import auth
from app.models import user
from app.routes import google_auth

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(google_auth.router, prefix="/auth", tags=["Google Auth"])


@app.get("/")
def root():
    return {"message": "Hello from FastAPI 🚀"}