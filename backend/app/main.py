from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routes import ai_assist, ai_usage, assistant, batch_assess, bulk_reports, dossier, gradebook, modules, report_download, reviews, smart_drop, statistics, streaming, students, uploads
from app.storage import ensure_bucket

app = FastAPI(title="Submission Review Interface API")

app.add_middleware(
    CORSMiddleware,
    # LAN-only local tool, no cookies/credentials used - wildcard is fine and avoids
    # having to enumerate every device's origin (localhost, LAN IP, hostname, ...).
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(modules.router)
app.include_router(students.router)
app.include_router(reviews.router)
app.include_router(ai_assist.router)
app.include_router(ai_usage.router)
app.include_router(assistant.router)
app.include_router(statistics.router)
app.include_router(uploads.router)
app.include_router(dossier.router)
app.include_router(report_download.router)
app.include_router(gradebook.router)
app.include_router(bulk_reports.router)
app.include_router(smart_drop.router)
app.include_router(streaming.router)
app.include_router(batch_assess.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    try:
        ensure_bucket()
    except Exception as e:
        print(f"Warning: could not reach MinIO at startup ({e}); uploads will retry per-call.")


@app.get("/api/health")
def health():
    return {"status": "ok"}
