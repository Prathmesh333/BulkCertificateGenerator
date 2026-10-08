import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    database_url: str = "sqlite:///./storage/certificates.db"
    storage_dir: Path = Path("storage")
    template_dir: Path = Path(__file__).parent / "templates" / "default"
    max_recipients: int = 1000
    max_attempts: int = 3
    poll_seconds: float = 1
    serverless: bool = False
    s3_bucket: str = ""
    s3_endpoint: str | None = None
    batch_size: int = 10
    upload_limit: int = 10 * 1024 * 1024

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.getenv("DATABASE_URL", cls.database_url),
            storage_dir=Path(os.getenv("STORAGE_DIR", "/tmp/certificates" if os.getenv("VERCEL") else "storage")),
            template_dir=Path(os.getenv("TEMPLATE_DIR", str(cls.template_dir))),
            max_recipients=int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000")),
            max_attempts=int(os.getenv("MAX_PROCESSING_ATTEMPTS", "3")),
            poll_seconds=float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "1")),
            serverless=os.getenv("PROCESSING_MODE") == "serverless",
            s3_bucket=os.getenv("S3_BUCKET", ""),
            s3_endpoint=os.getenv("S3_ENDPOINT_URL"),
            batch_size=int(os.getenv("PROCESSING_BATCH_SIZE", "10")),
            upload_limit=int(os.getenv("MAX_UPLOAD_BYTES", "3000000" if os.getenv("VERCEL") else "10485760")),
        )
