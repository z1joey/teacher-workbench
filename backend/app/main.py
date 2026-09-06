from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import get_current_user
from .routers import admin, auth, classes, dashboard, exams, misc, profile, students

app = FastAPI(title="Teacher Workbench API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(students.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(classes.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(exams.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(misc.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(dashboard.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(profile.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
