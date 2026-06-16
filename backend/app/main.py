from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.events import router as events_router
from app.api.me import router as me_router
from app.config import settings
from app.database import Base, engine
from app.models import economic_event, user_settings

app = FastAPI(title="Trader Mini Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(events_router, prefix="/api/v1/events", tags=["events"])
app.include_router(me_router, prefix="/api/v1/me", tags=["me"])


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
