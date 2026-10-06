import io

from fastapi.testclient import TestClient
from openpyxl import Workbook
from PIL import Image
from pypdf import PdfReader

from app.config import Settings
from app.main import create_app
from app.worker import process_next


def test_uploaded_design_excel_and_custom_fields(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", storage_dir=tmp_path / "storage")
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        image = io.BytesIO()
        Image.new("RGB", (1200, 850), "white").save(image, format="PNG")
        background = client.post("/builder/images", files={"file": ("design.png", image.getvalue(), "image/png")}).json()
        workbook = Workbook()
        workbook.active.append(["Name", "Number"])
        workbook.active.append(["Aisha Khan", "00123"])
        workbook.active.append([None, "456"])
        data = io.BytesIO()
        workbook.save(data)
        sheet = client.post("/builder/sheets", files={"file": ("data.xlsx", data.getvalue())}).json()
        assert sheet["rows"][0]["Number"] == "00123"
        payload = {"image_id": background["image_id"], "sheet_id": sheet["sheet_id"], "name_column": "Name",
                   "fields": [{"column": "Name", "x_mm": 148, "y_mm": 90, "max_width_mm": 200},
                              {"column": "Number", "x_mm": 148, "y_mm": 120, "max_width_mm": 200}]}
        response = client.post("/builder/jobs", json=payload)
        assert response.status_code == 202
        assert response.json()["accepted"] == 1
        assert response.json()["rejected"] == 1
        job = response.json()["job_id"]
        # Uploaded image mutation must not affect the copied job snapshot.
        (settings.storage_dir / "uploads" / f"{background['image_id']}.png").unlink()
        process_next(app.state.sessions, settings, app.state.renderer)
        assert client.get(f"/jobs/{job}").json()["status"] == "completed_with_errors"
        result = client.get(f"/jobs/{job}/recipients").json()["items"][0]
        pdf = PdfReader(io.BytesIO(client.get(result["download_url"]).content))
        text = pdf.pages[0].extract_text()
        assert "Aisha Khan" in text and "00123" in text
        assert len(pdf.pages[0].images) == 1
        assert client.get(f"/jobs/{job}/download").status_code == 200
        payload["fields"][0]["column"] = "Missing"
        assert client.post("/builder/jobs", json=payload).status_code == 404


def test_upload_validation(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", storage_dir=tmp_path / "storage"))
    with TestClient(app) as client:
        assert client.post("/builder/images", files={"file": ("bad.png", b"not an image")}).status_code == 422
        for value in [b"Name,Name\nA,B", b"Name,\nA,B", b"Name\n", b"Name\nA,extra"]:
            assert client.post("/builder/sheets", files={"file": ("bad.csv", value)}).status_code == 422
        assert client.get("/builder/images/not-a-uuid").status_code == 422
