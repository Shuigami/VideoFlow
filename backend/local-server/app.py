"""
Serveur local VideoFlow — simule l'architecture serverless complète sans AWS.

Usage:
    cd backend/local-server
    pip install -r requirements.txt
    uvicorn app:app --reload --port 8000

Frontend:
    VITE_API_URL=http://localhost:8000
    VITE_WS_URL=ws://localhost:8000/ws
    VITE_MOCK_API=false
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from video_processor import process_video  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
JOBS_FILE = DATA_DIR / "jobs.json"

app = FastAPI(title="VideoFlow Local Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, dict[str, Any]] = {}
job_subscribers: dict[str, set[WebSocket]] = {}
connections: dict[WebSocket, str | None] = {}


class CreateJobRequest(BaseModel):
    filename: str
    contentType: str = "video/mp4"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_jobs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_FILE.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def load_jobs() -> None:
    if JOBS_FILE.exists():
        jobs.update(json.loads(JOBS_FILE.read_text(encoding="utf-8")))


def enrich_job(job: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(job)
    base_url = "http://localhost:8000/media"
    job_id = job["jobId"]

    if job.get("outputs"):
        enriched["outputUrls"] = {
            quality: f"{base_url}/{job_id}/{quality}.mp4" for quality in job["outputs"]
        }
    if job.get("thumbnailKey"):
        enriched["thumbnailUrl"] = f"{base_url}/{job_id}/thumbnail.jpg"
    return enriched


async def broadcast_job(job_id: str) -> None:
    if job_id not in jobs:
        return

    payload = enrich_job(jobs[job_id])
    message = json.dumps({"type": "job_update", "job": payload})
    dead: list[WebSocket] = []

    for ws in job_subscribers.get(job_id, set()):
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)

    for ws in dead:
        job_subscribers.get(job_id, set()).discard(ws)


async def process_job_async(job_id: str, source_path: Path) -> None:
    try:
        jobs[job_id]["status"] = "PROCESSING"
        jobs[job_id]["updatedAt"] = now_iso()
        jobs[job_id]["processingStartedAt"] = now_iso()
        save_jobs()
        await broadcast_job(job_id)

        output_dir = PROCESSED_DIR / job_id
        result = await asyncio.to_thread(process_video, source_path, output_dir)

        output_keys = {quality: f"{quality}.mp4" for quality in result["outputs"]}
        jobs[job_id].update(
            {
                "status": "COMPLETED",
                "updatedAt": now_iso(),
                "completedAt": now_iso(),
                "metadata": result["metadata"],
                "outputs": output_keys,
                "thumbnailKey": "thumbnail.jpg",
                "message": "Traitement terminé (serveur local — FFmpeg).",
            }
        )
        save_jobs()
        await broadcast_job(job_id)

    except Exception as exc:
        jobs[job_id].update(
            {
                "status": "FAILED",
                "updatedAt": now_iso(),
                "failedAt": now_iso(),
                "error": str(exc),
            }
        )
        save_jobs()
        await broadcast_job(job_id)


@app.on_event("startup")
async def startup() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    load_jobs()


@app.get("/health")
async def health() -> dict[str, str]:
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    return {"status": "ok", "ffmpeg": "available" if ffmpeg_ok else "missing"}


@app.post("/jobs")
async def create_job(body: CreateJobRequest) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    timestamp = now_iso()
    extension = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else "mp4"

    jobs[job_id] = {
        "jobId": job_id,
        "filename": body.filename,
        "contentType": body.contentType,
        "status": "PENDING",
        "s3Key": f"uploads/{job_id}/source.{extension}",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    save_jobs()

    return {
        "jobId": job_id,
        "uploadUrl": f"http://localhost:8000/upload/{job_id}",
        "status": "PENDING",
        "expiresIn": 3600,
    }


@app.put("/upload/{job_id}")
async def receive_upload(job_id: str, request: Request) -> dict[str, str]:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    extension = jobs[job_id]["filename"].rsplit(".", 1)[-1].lower()
    source_path = job_dir / f"source.{extension}"

    body = await request.body()
    source_path.write_bytes(body)

    jobs[job_id].update(
        {
            "status": "UPLOADED",
            "updatedAt": now_iso(),
            "uploadedAt": now_iso(),
            "localSourcePath": str(source_path),
        }
    )
    save_jobs()

    return {"message": "Upload received"}


@app.post("/jobs/{job_id}/confirm")
async def confirm_upload(job_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] == "PENDING":
        raise HTTPException(status_code=400, detail="Upload not received yet")

    if job["status"] == "UPLOADED":
        extension = job["filename"].rsplit(".", 1)[-1].lower()
        source_path = UPLOAD_DIR / job_id / f"source.{extension}"
        background_tasks.add_task(process_job_async, job_id, source_path)
        job["message"] = "Événement Video Uploaded simulé — pipeline FFmpeg démarré."
        save_jobs()

    return enrich_job(jobs[job_id])


@app.get("/jobs")
async def list_jobs() -> dict[str, Any]:
    ordered = sorted(jobs.values(), key=lambda item: item.get("createdAt", ""), reverse=True)
    return {"jobs": [enrich_job(job) for job in ordered], "count": len(ordered)}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return enrich_job(jobs[job_id])


@app.get("/media/{job_id}/{filename}")
async def serve_media(job_id: str, filename: str) -> FileResponse:
    file_path = PROCESSED_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "image/jpeg" if filename.endswith(".jpg") else "video/mp4"
    return FileResponse(file_path, media_type=media_type)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    connections[websocket] = None

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            if payload.get("action") != "subscribe":
                continue

            job_id = payload.get("jobId")
            if not job_id:
                await websocket.send_text(json.dumps({"error": "jobId required"}))
                continue

            connections[websocket] = job_id
            job_subscribers.setdefault(job_id, set()).add(websocket)

            if job_id in jobs:
                await websocket.send_text(
                    json.dumps({"type": "job_update", "job": enrich_job(jobs[job_id])})
                )
            else:
                await websocket.send_text(json.dumps({"type": "subscribed", "jobId": job_id}))
    except WebSocketDisconnect:
        pass
    finally:
        job_id = connections.pop(websocket, None)
        if job_id and job_id in job_subscribers:
            job_subscribers[job_id].discard(websocket)
