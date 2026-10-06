import logging
import time

from filelock import FileLock
from sqlalchemy import select

from app.config import Settings
from app.database import Item, Job, connect, now
from app.renderer import Renderer

log = logging.getLogger(__name__)


def finish(session, job):
    states = list(session.scalars(select(Item.status).where(Item.job_id == job.id)))
    if any(state in ("pending", "processing") for state in states):
        return
    successes = states.count("succeeded")
    job.status = "completed" if successes == len(states) else "completed_with_errors" if successes else "failed"
    job.completed_at = now()


def recover(sessions, settings):
    with sessions.begin() as session:
        for item in session.scalars(select(Item).where(Item.status == "processing")):
            if item.attempt_count >= settings.max_attempts:
                item.status = "failed"
                item.error_stage = "processing"
                item.error_code = "ATTEMPTS_EXHAUSTED"
                item.error_message = "Processing was interrupted too many times."
                item.completed_at = now()
            else:
                item.status = "pending"
        for job in session.scalars(select(Job).where(Job.status.in_(["queued", "processing"]))):
            finish(session, job)


def process_next(sessions, settings, renderer):
    with sessions.begin() as session:
        job = session.scalar(select(Job).where(Job.status.in_(["queued", "processing"])).order_by(Job.created_at, Job.id).limit(1))
        if job is None:
            return False
        job.status = "processing"
        job.started_at = job.started_at or now()
        job_id = job.id
    while True:
        with sessions.begin() as session:
            job = session.get(Job, job_id)
            item = session.scalar(select(Item).where(Item.job_id == job_id, Item.status == "pending").order_by(Item.input_index).limit(1))
            if item is None:
                finish(session, job)
                break
            item.status = "processing"
            item.attempt_count += 1
            item.started_at = now()
        key = f"certificates/{job.id}/{item.certificate_id}.pdf"
        target = settings.storage_dir / key
        temporary = target.with_suffix(".tmp")
        error = None
        stage = "storage"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            stage = "rendering"
            renderer.render(job, item, temporary)
            stage = "storage"
            temporary.replace(target)
        except Exception as exc:
            log.exception("Certificate failed: job=%s item=%s", job.id, item.id)
            error = str(exc) if isinstance(exc, ValueError) else "Certificate generation failed."
        finally:
            temporary.unlink(missing_ok=True)
        with sessions.begin() as session:
            record = session.get(Item, item.id)
            record.status = "failed" if error else "succeeded"
            record.completed_at = now()
            if error:
                record.error_stage = stage
                record.error_code = "GENERATION_FAILED"
                record.error_message = error
            else:
                record.output_key = key
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    engine, sessions = connect(settings)
    renderer = Renderer(settings.template_dir)
    try:
        with FileLock(str(settings.storage_dir / "worker.lock"), timeout=0):
            recover(sessions, settings)
            while True:
                if not process_next(sessions, settings, renderer):
                    time.sleep(settings.poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
