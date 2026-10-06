import json
import tempfile
import zipfile
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from starlette.background import BackgroundTask

from app.config import Settings
from app.database import Item, Job, connect, identifier, now
from app.renderer import Renderer
from app.schemas import Recipient, Request
from app.builder import install_builder


def item_result(item):
    return {
        "index": item.input_index, "reference": item.client_reference,
        "name": item.recipient_name, "status": item.status,
        "certificate_id": item.certificate_id,
        "download_url": f"/jobs/{item.job_id}/certificates/{item.certificate_id}" if item.status == "succeeded" else None,
        "error": {"stage": item.error_stage, "code": item.error_code, "message": item.error_message} if item.error_code else None,
    }


def create_app(settings=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        engine, sessions = connect(settings)
        app.state.sessions = sessions
        app.state.renderer = Renderer(settings.template_dir)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Bulk Certificate Generator", lifespan=lifespan)
    install_builder(app, settings)

    def get_job(session, job_id):
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found.")
        return job

    @app.post("/jobs", status_code=202)
    def create_job(payload: Request, response: Response):
        if len(payload.recipients) > settings.max_recipients:
            raise HTTPException(422, f"At most {settings.max_recipients} recipients are allowed.")
        with app.state.sessions.begin() as session:
            job = Job(course_name=payload.course_name, issue_date=payload.issue_date.isoformat(),
                      total_count=len(payload.recipients), template_version=app.state.renderer.version)
            session.add(job)
            session.flush()
            accepted = 0
            for index, raw in enumerate(payload.recipients):
                item = Item(job_id=job.id, input_index=index, status="failed")
                try:
                    recipient = Recipient.model_validate(raw)
                    item.recipient_name = recipient.name
                    item.email = str(recipient.email) if recipient.email else None
                    item.client_reference = recipient.reference
                    item.certificate_id = identifier()
                    item.status = "pending"
                    accepted += 1
                except ValidationError as exc:
                    first = exc.errors(include_url=False)[0]
                    item.error_stage = "validation"
                    item.error_code = "INVALID_RECIPIENT"
                    item.error_message = f"{'.'.join(map(str, first['loc'])) or 'recipient'}: {first['msg']}"
                    item.completed_at = now()
                    if isinstance(raw, dict):
                        for source, dest in (("name", "recipient_name"), ("reference", "client_reference")):
                            value = raw.get(source)
                            if isinstance(value, str):
                                setattr(item, dest, value[:150])
                session.add(item)
            if not accepted:
                job.status = "failed"
                job.completed_at = now()
                response.status_code = 201
            response.headers["Location"] = f"/jobs/{job.id}"
            return {"job_id": job.id, "status": job.status, "total": job.total_count,
                    "accepted": accepted, "rejected": job.total_count - accepted,
                    "status_url": f"/jobs/{job.id}"}

    @app.get("/jobs/{job_id}")
    def progress(job_id: str):
        with app.state.sessions() as session:
            job = get_job(session, job_id)
            counts = dict.fromkeys(["pending", "processing", "succeeded", "failed"], 0)
            counts.update(dict(session.execute(select(Item.status, func.count()).where(Item.job_id == job_id).group_by(Item.status)).all()))
            processed = counts["succeeded"] + counts["failed"]
            return {"job_id": job.id, "status": job.status, "course_name": job.course_name,
                    "issue_date": job.issue_date, "total": job.total_count, "counts": counts,
                    "processed": processed, "progress_percent": round(processed / job.total_count * 100, 2),
                    "created_at": job.created_at, "started_at": job.started_at, "completed_at": job.completed_at}

    @app.get("/jobs/{job_id}/recipients")
    def results(job_id: str, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
                status: Literal["pending", "processing", "succeeded", "failed"] | None = None):
        with app.state.sessions() as session:
            get_job(session, job_id)
            query = select(Item).where(Item.job_id == job_id)
            if status:
                query = query.where(Item.status == status)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            items = session.scalars(query.order_by(Item.input_index).offset(offset).limit(limit))
            return {"items": [item_result(item) for item in items], "total": total, "limit": limit, "offset": offset}

    @app.get("/jobs/{job_id}/certificates/{certificate_id}")
    def certificate(job_id: str, certificate_id: str):
        with app.state.sessions() as session:
            item = session.scalar(select(Item).where(Item.job_id == job_id, Item.certificate_id == certificate_id))
            if item is None:
                raise HTTPException(404, "Certificate not found.")
            if item.status != "succeeded":
                raise HTTPException(409, "Certificate is not available.")
            path = settings.storage_dir / item.output_key
            if not path.is_file():
                raise HTTPException(404, "Certificate file is missing.")
            return FileResponse(path, media_type="application/pdf", filename=f"{certificate_id}.pdf")

    @app.get("/jobs/{job_id}/download")
    def archive(job_id: str):
        with app.state.sessions() as session:
            job = get_job(session, job_id)
            if job.status in ("queued", "processing"):
                raise HTTPException(409, "Job is still running.")
            items = list(session.scalars(select(Item).where(Item.job_id == job_id).order_by(Item.input_index)))
            successful = [item for item in items if item.status == "succeeded"]
            if not successful:
                raise HTTPException(409, "No successful certificates are available.")
            temporary_dir = tempfile.TemporaryDirectory(prefix="certificate-download-")
            from pathlib import Path
            path = Path(temporary_dir.name) / "certificates.zip"
            try:
                with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as output:
                    for item in successful:
                        source = settings.storage_dir / item.output_key
                        if not source.is_file():
                            raise HTTPException(404, "A certificate file is missing.")
                        output.write(source, f"{item.certificate_id}.pdf")
                    output.writestr("manifest.json", json.dumps([item_result(item) for item in items], indent=2))
            except BaseException:
                temporary_dir.cleanup()
                raise
            return FileResponse(path, media_type="application/zip", filename=f"{job_id}.zip",
                                background=BackgroundTask(temporary_dir.cleanup))

    return app


app = create_app()
