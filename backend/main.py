import logging
from contextlib import asynccontextmanager


from fastapi import Depends,FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

import models #noqa registers the tables on base before create_all
from db import Base, engine, get_db


logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app:FastAPI):
    # creates table that doesnt exist yet (never cahnges existing ones)

    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="API", lifespan=lifespan)



@app.get("/health")
def health(db: Session = Depends(get_db)):
    """200 only when database answers too"""
    try: 
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        return JSONResponse(status_code=503, content={"status": "error", "database":"down"})
    # return {"st}
    return {"status": "ok!", "database":"ok"}


@app.post("/chat")
def chat():
    pass
