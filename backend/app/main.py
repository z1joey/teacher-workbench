from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .deps import get_current_teacher
from .routers import admin, auth, classes, dashboard, exams, misc, profile, students

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Teacher Workbench API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(students.router, prefix="/api", dependencies=[Depends(get_current_teacher)])
app.include_router(classes.router, prefix="/api", dependencies=[Depends(get_current_teacher)])
app.include_router(exams.router, prefix="/api", dependencies=[Depends(get_current_teacher)])
app.include_router(misc.router, prefix="/api", dependencies=[Depends(get_current_teacher)])
app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(get_current_teacher)])
app.include_router(profile.router, prefix="/api", dependencies=[Depends(get_current_teacher)])
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
