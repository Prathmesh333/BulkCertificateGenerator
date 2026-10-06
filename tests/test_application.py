import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select

from app.config import Settings
from app.database import Item
from app.main import create_app
from app.worker import process_next, recover


@pytest.fixture
def system(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", storage_dir=tmp_path / "storage")
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, app, settings


def submit(client, recipients=None):
    return client.post("/jobs", json={"course_name": "Python Course", "issue_date": "2026-10-06",
                                     "recipients": recipients if recipients is not None else [{"name": "Aisha Khan"}]})


def test_complete_workflow(system):
    client, app, settings = system
    response = submit(client, [{"name": "Aisha Khan"}, {"name": ""}, {"name": "Rahul Sharma"}])
    assert response.status_code == 202
    job = response.json()["job_id"]
    assert response.json()["accepted"] == 2
    assert client.get(f"/jobs/{job}").json()["counts"]["failed"] == 1
    assert client.get(f"/jobs/{job}/download").status_code == 409
    assert process_next(app.state.sessions, settings, app.state.renderer)
    progress = client.get(f"/jobs/{job}").json()
    assert progress["status"] == "completed_with_errors"
    assert progress["progress_percent"] == 100
    assert progress["counts"] == {"pending": 0, "processing": 0, "succeeded": 2, "failed": 1}
    results = client.get(f"/jobs/{job}/recipients").json()["items"]
    pdf = client.get(results[0]["download_url"])
    assert pdf.headers["content-type"] == "application/pdf"
    reader = PdfReader(io.BytesIO(pdf.content))
    assert len(reader.pages) == 1
    assert "Aisha Khan" in reader.pages[0].extract_text()
    assert float(reader.pages[0].mediabox.width) == pytest.approx(841.89, abs=.1)
    archive = client.get(f"/jobs/{job}/download")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as output:
        assert len(output.namelist()) == 3
        assert len(json.loads(output.read("manifest.json"))) == 3
    assert client.get(f"/jobs/{job}/recipients?status=failed").json()["total"] == 1
    assert not process_next(app.state.sessions, settings, app.state.renderer)


@pytest.mark.parametrize("patch", [{"course_name": " "}, {"issue_date": "bad"}, {"recipients": []}, {"recipients": "bad"}])
def test_request_validation(system, patch):
    client, _, _ = system
    payload = {"course_name": "Python", "issue_date": "2026-10-06", "recipients": [{"name": "A"}]}
    payload.update(patch)
    assert client.post("/jobs", json=payload).status_code == 422


def test_invalid_recipients_and_limits(system):
    client, _, settings = system
    response = submit(client, [None, {"name": "Valid", "email": "invalid"}, {"name": "नमस्ते"}])
    assert response.status_code == 201
    job = response.json()["job_id"]
    assert client.get(f"/jobs/{job}").json()["status"] == "failed"
    assert client.get(f"/jobs/{job}/download").status_code == 409
    settings.max_recipients = 1
    assert submit(client, [{"name": "A"}, {"name": "B"}]).status_code == 422


def test_individual_failure(system):
    client, app, settings = system
    job = submit(client, [{"name": "Failure"}, {"name": "Success"}]).json()["job_id"]
    original = app.state.renderer.render
    def render(job, item, target):
        if item.recipient_name == "Failure":
            raise RuntimeError("private internal information")
        original(job, item, target)
    app.state.renderer.render = render
    process_next(app.state.sessions, settings, app.state.renderer)
    items = client.get(f"/jobs/{job}/recipients").json()["items"]
    assert [item["status"] for item in items] == ["failed", "succeeded"]
    assert "private" not in items[0]["error"]["message"]


def test_recovery_and_download_isolation(system):
    client, app, settings = system
    job = submit(client).json()["job_id"]
    with app.state.sessions.begin() as session:
        item = session.scalar(select(Item).where(Item.job_id == job))
        item.status = "processing"
        item.attempt_count = 1
        certificate_id = item.certificate_id
    assert client.get(f"/jobs/{job}/certificates/{certificate_id}").status_code == 409
    recover(app.state.sessions, settings)
    process_next(app.state.sessions, settings, app.state.renderer)
    assert client.get(f"/jobs/{job}").json()["status"] == "completed"
    assert client.get(f"/jobs/another/certificates/{certificate_id}").status_code == 404
    recover(app.state.sessions, settings)
    assert not process_next(app.state.sessions, settings, app.state.renderer)


def test_attempt_exhaustion(system):
    client, app, settings = system
    job = submit(client).json()["job_id"]
    with app.state.sessions.begin() as session:
        item = session.scalar(select(Item).where(Item.job_id == job))
        item.status = "processing"
        item.attempt_count = settings.max_attempts
    recover(app.state.sessions, settings)
    assert client.get(f"/jobs/{job}").json()["status"] == "failed"


def test_text_overflow(system):
    client, app, settings = system
    job = submit(client, [{"name": "W" * 150}]).json()["job_id"]
    process_next(app.state.sessions, settings, app.state.renderer)
    result = client.get(f"/jobs/{job}/recipients").json()["items"][0]
    assert result["status"] == "failed"
    assert "cannot fit" in result["error"]["message"]


def test_canva_background_and_font_shrinking(system, tmp_path):
    from PIL import Image
    from app.renderer import Renderer
    client, app, settings = system
    layout = json.loads((settings.template_dir / "layout.json").read_text())
    (tmp_path / "layout.json").write_text(json.dumps(layout))
    Image.new("RGB", (1200, 850), "white").save(tmp_path / "background.png")
    renderer = Renderer(tmp_path)
    job = submit(client, [{"name": "W" * 30}]).json()["job_id"]
    process_next(app.state.sessions, settings, renderer)
    item = client.get(f"/jobs/{job}/recipients").json()["items"][0]
    assert item["status"] == "succeeded"
    pdf = PdfReader(io.BytesIO(client.get(item["download_url"]).content))
    assert len(pdf.pages[0].images) == 1
    assert "W" * 30 in pdf.pages[0].extract_text()


def test_missing_files_and_unknown_jobs(system):
    client, app, settings = system
    assert client.get("/jobs/unknown").status_code == 404
    job = submit(client).json()["job_id"]
    process_next(app.state.sessions, settings, app.state.renderer)
    with app.state.sessions() as session:
        item = session.scalar(select(Item).where(Item.job_id == job))
        (settings.storage_dir / item.output_key).unlink()
    assert client.get(f"/jobs/{job}/certificates/{item.certificate_id}").status_code == 404
    assert client.get(f"/jobs/{job}/download").status_code == 404
