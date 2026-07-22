from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine
from app.db import base  
from app.api.v1.routes import api_router

app = FastAPI(title="Doctor-Patient Reports API")

# Allow your separately-hosted frontend to call this API.
# Replace "*" with your actual frontend URL(s) in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def on_startup():
    # For quick local development only. Once you add Alembic migrations,
    # remove this and rely on `alembic upgrade head` instead.
    base.Base.metadata.create_all(bind=engine)


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Doctor-Patient Reports API"}
