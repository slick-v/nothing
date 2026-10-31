import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal, get_db
from app.routes.ask import router as ask_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.services.rag import get_model

logger = logging.getLogger(__name__)
FRONTEND_PAGE = Path(__file__).resolve().parents[2] / "frontend" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # a job that was running when the server stopped will never finish, so say so
    with SessionLocal() as db:
        db.execute(
            update(models.Document)
            .where(models.Document.status == "processing")
            .values(status="failed", error="The server restarted during processing. Upload it again.")
        )
        db.commit()
    get_model()   # load now, so the first question isn't slowed down
    yield


app = FastAPI(title="API", lifespan=lifespan)

app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(ask_router)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """200 only when the database answers too."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        return JSONResponse(status_code=503, content={"status": "error", "database": "down"})
    return {"status": "ok!", "database": "ok"}


@app.get("/", include_in_schema=False)
def home():
    """The chat page (served from here, so no CORS setup is needed)."""
    return FileResponse(FRONTEND_PAGE)
