import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


class Renderer:
    def __init__(self, template_dir):
        self.directory = Path(template_dir)
        self.layout = json.loads((self.directory / "layout.json").read_text())
        self.version = self.layout["version"]
        # Standard PDF fonts provide an explicit, portable ASCII-only baseline.
        for field in self.layout["fields"].values():
            stringWidth("sample", field["font"], field["font_size_pt"])

    def render(self, job, item, destination, custom_values=None):
        if job.template_version != self.version:
            raise ValueError("Job template version is unavailable.")
        width = self.layout["page"]["width_mm"] * mm
        height = self.layout["page"]["height_mm"] * mm
        canvas = Canvas(str(destination), pagesize=(width, height))
        canvas.setTitle("Certificate of Completion")
        background = self.directory / "background.png"
        if background.exists():
            canvas.drawImage(str(background), 0, 0, width, height)
        else:
            # A built-in vector design makes the project usable without Canva assets.
            canvas.setStrokeColor(HexColor("#b18c42"))
            canvas.setLineWidth(3)
            canvas.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
            canvas.setFillColor(HexColor("#203040"))
            canvas.setFont("Helvetica-Bold", 30)
            canvas.drawCentredString(width / 2, height - 48 * mm, "CERTIFICATE OF COMPLETION")
            canvas.setFont("Helvetica", 14)
            canvas.drawCentredString(width / 2, height - 72 * mm, "This certificate is presented to")
            canvas.drawCentredString(width / 2, height - 111 * mm, "for successfully completing")
        values = {"recipient_name": item.recipient_name, "course_name": job.course_name,
                  "issue_date": "Issued on " + job.issue_date,
                  "certificate_id": "Certificate ID: " + item.certificate_id}
        if custom_values is not None:
            values = custom_values
        for key, field in self.layout["fields"].items():
            value = values[key]
            size = field["font_size_pt"]
            while stringWidth(value, field["font"], size) > field["max_width_mm"] * mm:
                size -= 1
                if size < field["min_font_size_pt"]:
                    raise ValueError(f"{key} cannot fit in its reserved space.")
            canvas.setFillColor(HexColor(field.get("color", "#203040")))
            canvas.setFont(field["font"], size)
            draw = {"center": canvas.drawCentredString, "left": canvas.drawString, "right": canvas.drawRightString}[field.get("align", "center")]
            draw(field["x_mm"] * mm, height - field["y_mm"] * mm, value)
        canvas.showPage()
        canvas.save()
