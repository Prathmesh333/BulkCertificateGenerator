"""Bounded processing and durable-storage regression tests, without credentials."""
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.database import Item
from app.main import create_app
from app.storage import Storage
from app.worker import process_next


def test_batches_resume_and_isolate_jobs(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'db'}", storage_dir=tmp_path / "files")
    app = create_app(settings)
    with TestClient(app) as client:
        def submit():
            return client.post('/jobs', json={"course_name": "Demo", "issue_date": "2026-10-08",
                "recipients": [{"name": "Demo Name"}, {"name": "Demo Recipient"}]}).json()['job_id']
        first, second = submit(), submit()
        assert client.get('/runtime').json()['processing_mode'] == 'worker'
        assert client.post(f'/jobs/{first}/process').status_code == 409
        process_next(app.state.sessions, settings, app.state.renderer, first, 1)
        progress = client.get(f'/jobs/{first}').json()
        assert progress['counts']['succeeded'] == 1
        assert progress['status'] == 'processing'
        assert client.get(f'/jobs/{second}').json()['counts']['pending'] == 2
        process_next(app.state.sessions, settings, app.state.renderer, first, 1)
        assert client.get(f'/jobs/{first}').json()['status'] == 'completed'
        with app.state.sessions() as session:
            assert all(i.attempt_count == 1 for i in session.scalars(select(Item).where(Item.job_id == first)))


def test_remote_storage_survives_empty_working_directory(tmp_path):
    class FakeS3:
        objects = {}
        def upload_file(self, path, bucket, key):
            self.objects[bucket, key] = Path(path).read_bytes()
        def download_file(self, bucket, key, path):
            Path(path).write_bytes(self.objects[bucket, key])
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert ExpiresIn == 600
            return 'https://storage.example/' + Params['Key']
    settings = SimpleNamespace(storage_dir=tmp_path, s3_bucket='')
    storage = Storage(settings)
    storage.client, storage.bucket = FakeS3(), 'private'
    target = tmp_path / 'certificates' / 'demo.pdf'
    target.parent.mkdir()
    target.write_bytes(b'%PDF-demo')
    storage.save(target)
    target.unlink()
    assert storage.load(target)
    assert target.read_bytes() == b'%PDF-demo'
    assert storage.url(target, 'demo.pdf').endswith('certificates/demo.pdf')


def test_serverless_requires_durable_dependencies():
    import pytest
    with pytest.raises(ValueError, match='PostgreSQL'):
        create_app(Settings(serverless=True))
