from fastapi import FastAPI
from app.api.routes import router
from app.core.database import Base, engine

# Create SQLite tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MoinSystems AI DevFlow Copilot",
    version="0.1.0-day1",
    description="Local-first GenAI requirement specification pipeline.",
)

app.include_router(router)