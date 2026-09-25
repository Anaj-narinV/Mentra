from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.database.session import Base, engine
from app.models import models  # noqa: F401 - ensures models are registered before create_all

from app.auth.router import router as auth_router
from app.profile.router import router as profile_router
from app.goals.router import router as goals_router
from app.roadmap.router import router as roadmap_router
from app.tasks.router import router as tasks_router
from app.conversation.router import router as conversation_router
from app.progress.router import router as progress_router
from app.adaptation.router import router as adaptation_router
from app.notifications.router import router as notifications_router

app = FastAPI(title="Mentra API", version="0.4.0", description="Mentra — AI Adaptive Mentoring Platform backend (Phase 4)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(goals_router)
app.include_router(roadmap_router)
app.include_router(tasks_router)
app.include_router(conversation_router)
app.include_router(progress_router)
app.include_router(adaptation_router)
app.include_router(notifications_router)
