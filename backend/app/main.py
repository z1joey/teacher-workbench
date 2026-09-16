from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .bootstrap_db import ensure_schema
from .database import engine
from .deps import get_current_user
from .routers import (
    admin,
    auth,
    classes,
    dashboard,
    data,
    exams,
    feedback,
    misc,
    profile,
    students,
    summaries,
)
from .version import APP_VERSION, IS_BETA


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    yield


app = FastAPI(title="Teacher Workbench API", version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(students.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(summaries.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(classes.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(exams.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(misc.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(profile.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(feedback.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(data.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"ok": True, "version": APP_VERSION, "beta": IS_BETA}
